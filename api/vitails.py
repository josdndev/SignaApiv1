import numpy as np
from scipy import signal

def extract_respiratory_rate(BVP_signal, FS):
    resp_LPF = 0.1
    resp_HPF = 0.5
    NyquistF = FS / 2.0
    if resp_LPF >= resp_HPF or resp_HPF >= NyquistF:
        return None
    try:
        B_resp, A_resp = signal.butter(2, [resp_LPF / NyquistF, resp_HPF / NyquistF], btype='bandpass')
        resp_signal = signal.filtfilt(B_resp, A_resp, BVP_signal)
    except Exception:
        return None
    min_resp_peak_dist = FS * (60.0 / 30.0)
    resp_peaks, _ = signal.find_peaks(resp_signal, distance=min_resp_peak_dist, prominence=np.std(resp_signal)*0.2)
    if len(resp_peaks) < 2:
        return None
    resp_intervals_sec = np.diff(resp_peaks) / FS
    valid_resp_intervals = resp_intervals_sec[(resp_intervals_sec >= 60.0/30.0) & (resp_intervals_sec <= 60.0/6.0)]
    if len(valid_resp_intervals) < 1:
        return None
    avg_resp_interval = np.mean(valid_resp_intervals)
    if avg_resp_interval <= 0: return None
    respiratory_rate = 60.0 / avg_resp_interval
    return respiratory_rate

def calculate_hrv(peaks, FS):
    if peaks is None or len(peaks) < 3:
        return None, None
    rr_intervals_ms = (np.diff(peaks) / FS) * 1000
    rr_intervals_ms_filtered = rr_intervals_ms[(rr_intervals_ms > 300) & (rr_intervals_ms < 2000)]
    if len(rr_intervals_ms_filtered) < 2:
        return None, None
    sdnn = np.std(rr_intervals_ms_filtered)
    rmssd = np.sqrt(np.mean(np.square(np.diff(rr_intervals_ms_filtered))))
    return sdnn, rmssd