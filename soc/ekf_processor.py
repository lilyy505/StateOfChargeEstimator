import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import json
import os
import math
import logging
from infra.message import Message
from infra.processor import Processor
from infra.utils import ArgumentSource

log = logging.getLogger(__name__)

# --- Physical Constants from kalman3.py ---
CELL_CAPACITY_AH = 3.5 
PARALLEL_STRINGS = 12
SERIES_CELLS = 34
PACK_CAPACITY_AH = CELL_CAPACITY_AH * PARALLEL_STRINGS 
R0_PACK_OHMS = 25.0 / 1000 * 34 / 12 
R1_PACK_OHMS = 0.0601 
C1_PACK_FARAD = 25.5 
SECONDS_PER_HOUR = 3600.0

class EKF_SOC_Processor(Processor):
    def __init__(self, arg_source: ArgumentSource):
        # 1. Load the OCV Map (Logic from kalman3.py)
        self._initialize_ocv_map()
        
        # 2. Persistence: Load last known state from JSON
        self.state_file = "soc/ekf_state.json"
        self.load_state()
        
        # 3. Filter Parameters
        self.P = np.diag([1e-3, 1e-4]) 
        self.Q = np.diag([1e-8, 1e-6]) 
        self.R = np.array([[0.05**2]]) 
        
        self.last_timestamp = None
        self.last_current = 0.0
        self.prev_used_coulombs = None 

    def _initialize_ocv_map(self):
        OCV_CSV_PATH = 'soc/curve-compute/processed_red_curve_data.csv'
        try:
            # Load logic exactly as seen in kalman3.py
            ocv_df = pd.read_csv(OCV_CSV_PATH)
            soc_points = ocv_df['State of Charge'].values * 100.0
            voltage_points = ocv_df['Voltage (V)'].values
            
            # Sort and scale for the pack (SERIES_CELLS = 34)
            sort_indices = np.argsort(soc_points)
            self.soc_to_ocv = interp1d(
                soc_points[sort_indices], 
                voltage_points[sort_indices] * SERIES_CELLS, 
                kind='linear', 
                fill_value="extrapolate"
            )
            print(f"Successfully loaded OCV curve from {OCV_CSV_PATH}")
            
        except Exception as e:
            print(f"Error loading OCV CSV: {e}. Using hardcoded fallback.")
            ocv_data = np.array([
                [0.0, 2.50],
                [50.0, 3.55],
                [100.0, 4.20]
            ])

            self.soc_to_ocv = interp1d(
                ocv_data[:, 0],
                ocv_data[:, 1] * SERIES_CELLS,
                kind='linear',
                fill_value="extrapolate"
            )

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                data = json.load(f)
                self.x = np.array([[data.get('soc', 0.8)], [data.get('vrc', 0.0)]])
        else:
            self.x = np.array([[0.8], [0.0]]) 

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump({"soc": float(self.x[0, 0]), "vrc": float(self.x[1, 0])}, f)

    def handle(self, messages: list[Message]) -> list[Message]:
        output_messages = []
        for msg in messages:
            if msg.telem_name == 'calculated_values.adjusted_coulomb_count':
                used_coulombs = float(msg.data['value'])
                now = msg.timestamp
                if self.prev_used_coulombs is not None and self.last_timestamp is not None:
                    dt = max((now - self.last_timestamp).total_seconds(), 1e-3)
                    delta_used_coulombs = used_coulombs - self.prev_used_coulombs

                    if delta_used_coulombs < 0:
                         self.prev_used_coulombs = used_coulombs
                         self.last_timestamp = now
                         continue
                
                    # Positive delta_used_coulombs means discharge, so SOC should go down
                    current_A = delta_used_coulombs / dt
            
                    # Predict State
                    A_rc = math.exp(-dt / (R1_PACK_OHMS * C1_PACK_FARAD))
                    B_rc = R1_PACK_OHMS * (1 - A_rc)

                    # SOC update from used coulombs
                    self.x[0, 0] -= delta_used_coulombs / (PACK_CAPACITY_AH * SECONDS_PER_HOUR)
                    self.x[0, 0] = np.clip(self.x[0, 0], 0.0, 1.0)

                    self.x[1, 0] = self.x[1, 0] * A_rc + current_A * B_rc

                    # Update Covariance
                    A_jac = np.array([[1.0, 0.0], [0.0, A_rc]])
                    self.P = A_jac @ self.P @ A_jac.T + self.Q
                    self.last_current = current_A

                    self.prev_used_coulombs = used_coulombs
                    self.last_timestamp = now


            # Trigger Correction on Voltage Update
            elif msg.telem_name == 'bms.pack_voltage_V':
                v_meas = msg.data['value']
                
                # Measurement Prediction
                ocv_pred = self.soc_to_ocv(self.x[0, 0] * 100.0)
                v_pred = ocv_pred - self.x[1, 0] - (self.last_current * R0_PACK_OHMS)
                
                # Innovation and Gain
                y = v_meas - v_pred
                C_jac = np.array([[40.0, -1.0]]) # Simplified derivative
                S = C_jac @ self.P @ C_jac.T + self.R
                K = self.P @ C_jac.T @ np.linalg.inv(S)
                
                # Apply Correction
                self.x = self.x + K * y
                self.x[0, 0] = np.clip(self.x[0, 0], 0.0, 1.0)
                self.P = (np.eye(2) - K @ C_jac) @ self.P
                
                self.save_state()
            
                msg.data['internal_soc_val'] = float(self.x[0, 0] * 100.0)    

        return messages     
