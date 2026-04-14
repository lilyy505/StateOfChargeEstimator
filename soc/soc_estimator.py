import math
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from typing import override

from infra.utils import ArgumentSource
from infra.message import Message
from infra.processors.processor import Processor

# --- Configuration (Merged from both files) ---
CELL_CAPACITY_AH = 3.5 
PARALLEL_STRINGS = 12
SERIES_CELLS = 34
PACK_CAPACITY_AH = CELL_CAPACITY_AH * PARALLEL_STRINGS # 42.0 Ah
SECONDS_PER_HOUR = 3600.0

# --- Parameters (From simulation file) ---
R0_PACK_OHMS = 25.0 / 1000 * 34 / 12 
R1_PACK_OHMS = 0.0601 
C1_PACK_FARAD = 25.5 
OCV_CSV_PATH = 'soc/curve-compute/processed_red_curve_data.csv'

class EKF_SOCEstimator:
    """The 'Brain' - logic moved into a helper class for the Processor"""
    def __init__(self, initial_soc_percent, initial_vrc1_volt, soc_to_ocv_interp, dt_sec=0.5):
        self.dt = dt_sec
        self.Qn_Ah = PACK_CAPACITY_AH
        self.soc_to_ocv = soc_to_ocv_interp
        
        initial_soc = initial_soc_percent / 100.0 
        self.x = np.array([[initial_soc], [initial_vrc1_volt]])  
        self.P = np.diag([1e-3, 1e-4])
        self.Q = np.diag([1e-8, 1e-6]) 
        self.R = np.array([[0.05**2]]) 

        self.A_rc = math.exp(-self.dt / (R1_PACK_OHMS * C1_PACK_FARAD))
        self.B_rc = R1_PACK_OHMS * (1 - self.A_rc)
        self.last_current = 0.0

    def get_ocv_prime(self):
        delta = 0.001
        soc_est = self.x[0, 0] * 100.0
        ocv_plus = self.soc_to_ocv(min(100.0, soc_est + delta))
        ocv_minus = self.soc_to_ocv(max(0.0, soc_est - delta))
        return (ocv_plus - ocv_minus) / (2 * delta)

    def predict(self, current_amp, dt):
        self.dt = dt
        # Re-calculate RC parameters if dt changed
        self.A_rc = math.exp(-self.dt / (R1_PACK_OHMS * C1_PACK_FARAD))
        self.B_rc = R1_PACK_OHMS * (1 - self.A_rc)
        
        I = current_amp
        self.x[0, 0] -= (I * self.dt) / (self.Qn_Ah * SECONDS_PER_HOUR)
        self.x[0, 0] = np.clip(self.x[0, 0], 0.0, 1.0)
        self.x[1, 0] = self.x[1, 0] * self.A_rc + I * self.B_rc
        
        A_jac = np.array([[1.0, 0.0], [0.0, self.A_rc]])
        self.P = A_jac @ self.P @ A_jac.T + self.Q
        self.last_current = I

    def correct(self, measured_voltage):
        ocv_pred = self.soc_to_ocv(self.x[0, 0] * 100.0)
        V_t_pred = ocv_pred - self.x[1, 0] - self.last_current * R0_PACK_OHMS
        y = measured_voltage - V_t_pred
        ocv_prime = self.get_ocv_prime()
        C_jac = np.array([[ocv_prime * 100, -1.0]])
        S = C_jac @ self.P @ C_jac.T + self.R
        K = self.P @ C_jac.T @ np.linalg.inv(S)
        self.x = self.x + (K * float(y))
        self.x[0, 0] = np.clip(self.x[0, 0], 0.0, 1.0)
        self.P = (np.eye(2) - K @ C_jac) @ self.P
        return self.x[0, 0] * 100.0

class SOCEstimator(Processor):
    def __init__(self, arg_source: ArgumentSource):
        self.arg_source = arg_source
        self.ekf = None
        self.last_timestamp = None
        
        # Load OCV data during initialization
        self.soc_to_ocv_interp = self._load_ocv_map()

    def _load_ocv_map(self):
        try:
            ocv_df = pd.read_csv(OCV_CSV_PATH)
            soc_points = ocv_df['State of Charge'].to_numpy(dtype=float) * 100.0
            voltage_points = ocv_df['Voltage (V)'].to_numpy(dtype=float) * SERIES_CELLS
            # Sort for interpolation
            idx = np.argsort(soc_points)
            return interp1d(soc_points[idx], voltage_points[idx], fill_value="extrapolate")
        except Exception as e:
            # Fallback map from your file
            data = np.array([[0.0, 2.50], [50.0, 3.55], [100.0, 4.20]])
            return interp1d(data[:, 0], data[:, 1] * SERIES_CELLS, fill_value="extrapolate")

    @override
    def handle(self, messages: list[Message]) -> list[Message]:
        output_messages: list[Message] = []
        for msg in messages:
            # 1. Check if the EKF 'Brain' hid the value in the dictionary
            if 'internal_soc_val' in msg.data:
                soc_val = msg.data['internal_soc_val']
                
                # 2. Create the output message with the EXACT parameter names
                new_msg = Message(
                    can_id=0x3F3,               # Match the 'can_id' parameter name
                    data={"soc_ekf": soc_val},  # The dictionary for Grafana
                    timestamp=msg.timestamp,    # Pass the original timestamp
                    telem_name='soc_output'     # Give it a name for the logs
                )
                output_messages.append(new_msg)
                del msg.data['internal_soc_val']
            
            # 3. Optional: Remove the internal value so it's not sent to InfluxDB twice
            # del msg.data['internal_soc_val']
            
            # Optional: Clean up the temporary key so it doesn't stay in the pipeline
            # del msg.data['internal_soc_val']
            """
            # Assuming Message has .current_ma, .voltage_v, and .timestamp
            current_a = -msg.current_ma / 1000.0  # Sign correction from your simulation
            voltage_v = msg.voltage_v
            
            # ... inside the loop ...
            msg.soc_percent = soc_estimate
            print(f"Time: {msg.timestamp} | Voltage: {voltage_v:.2f}V | Estimated SOC: {soc_estimate:.2f}%")
            self.last_timestamp = msg.timestamp
            
            # Initialize EKF on the first message
            if self.ekf is None:
                # Initial guess: assume V = OCV - I*R0
                init_ocv = voltage_v + current_a * R0_PACK_OHMS
                # We need the inverse mapping here (Voltage -> SOC)
                # For simplicity, starting at 100% or calculating inverse:
                init_soc = 100.0 # Or implement ocv_to_soc_interp
                self.ekf = EKF_SOCEstimator(init_soc, 0.0, self.soc_to_ocv_interp)
                self.last_timestamp = msg.timestamp
                continue

            if self.last_timestamp:
                dt = (msg.timestamp - self.last_timestamp).total_seconds()
            else:
                dt = 0.5 # Default fallback
            
            self.ekf.predict(current_a, dt)
            soc_estimate = self.ekf.correct(voltage_v)
            
            # Update the message with the new SOC
            msg.soc_percent = soc_estimate
            self.last_timestamp = msg.timestamp
        """
        # print(soc_estimate)
        #print(msg.soc_percent)
        return messages + output_messages
