import numpy as np
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError as e:
    print(f"Warning: OpenCV not available: {e}")
    CV2_AVAILABLE = False

from scipy import signal

# Importar FaceDetector solo si OpenCV está disponible
if CV2_AVAILABLE:
    try:
        from cvzone.FaceDetectionModule import FaceDetector
        FACE_DETECTOR_AVAILABLE = True
    except ImportError as e:
        print(f"Warning: FaceDetector not available: {e}")
        FACE_DETECTOR_AVAILABLE = False
else:
    FACE_DETECTOR_AVAILABLE = False

def read_video_with_face_detection_and_FS(video_file_path):
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV is not available. Cannot process video.")
    
    if not FACE_DETECTOR_AVAILABLE:
        raise ImportError("FaceDetector is not available. Cannot process video.")
    
    cap = cv2.VideoCapture(video_file_path)
    FS = cap.get(cv2.CAP_PROP_FPS)
    if FS <= 0:
        FS = 30
    face_frames = []
    detector = FaceDetector(minDetectionCon=0.6)  # Menor umbral para aceptar más caras
    target_size = (128, 128)
    std_height, std_width = None, None
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        if frame.shape[0] < 32 or frame.shape[1] < 32:
            continue
        try:
            img_with_faces, bboxs = detector.findFaces(frame, draw=False)
        except Exception:
            continue
        if bboxs:
            # Buscar la cara más grande
            largest_bbox = None
            max_area = 0
            for bbox_info in bboxs:
                x, y, w, h = bbox_info['bbox']
                area = w * h
                if area > max_area:
                    max_area = area
                    largest_bbox = bbox_info['bbox']
            if largest_bbox:
                x, y, w, h = largest_bbox
                y1, y2 = max(0, y), min(frame.shape[0], y + h)
                x1, x2 = max(0, x), min(frame.shape[1], x + w)
                face_frame = frame[y1:y2, x1:x2]
                if face_frame.size == 0 or face_frame.shape[0] < 10 or face_frame.shape[1] < 10:
                    continue
                # Establecer tamaño estándar según la primera cara válida
                if std_height is None or std_width is None:
                    std_height, std_width = face_frame.shape[0], face_frame.shape[1]
                try:
                    face_frame_resized = cv2.resize(face_frame, (std_width, std_height), interpolation=cv2.INTER_AREA)
                    face_frame_rgb = cv2.cvtColor(face_frame_resized, cv2.COLOR_BGR2RGB)
                    # Detección de desenfoque
                    gray = cv2.cvtColor(face_frame_resized, cv2.COLOR_BGR2GRAY)
                    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
                    if fm < 10:  # umbral más bajo para aceptar más frames
                        continue
                    # Normalización
                    face_frame_rgb = face_frame_rgb.astype(np.float32) / 255.0
                    face_frames.append(face_frame_rgb)
                except Exception:
                    continue
    cap.release()
    if not face_frames:
        return None, None
    return face_frames, FS

def process_video(frames):
    RGB = []
    for frame in frames:
        if frame.size == 0:
            continue
        frame_area = frame.shape[0] * frame.shape[1]
        if frame_area > 0:
            sum_vals = np.sum(np.sum(frame, axis=0), axis=0)
            RGB.append(sum_vals / frame_area)
    RGB = np.asarray(RGB)
    # Filtro de frames atípicos (outliers por color)
    if len(RGB) > 10:
        medians = np.median(RGB, axis=0)
        stds = np.std(RGB, axis=0)
        mask = np.all(np.abs(RGB - medians) < 3 * stds, axis=1)
        RGB = RGB[mask]
    return RGB

def CHROME_DEHAAN(frames, FS):
    LPF, HPF = 0.7, 2.5
    WinSec = 1.6
    RGB = process_video(frames)
    FN = RGB.shape[0]
    NyquistF = FS / 2.0
    # Validar frecuencias de corte
    if LPF >= HPF or HPF >= NyquistF:
        HPF = min(HPF, NyquistF * 0.98)
        LPF = min(LPF, HPF * 0.98)
        if LPF <= 0: return None
    try:
        B, A = signal.butter(3, [LPF / NyquistF, HPF / NyquistF], btype='bandpass')
    except Exception:
        return None
    WinL = int(WinSec * FS)
    NWin = max(1, int((FN - WinL) / (WinL / 2)) + 1)
    S = np.zeros(FN)
    for i in range(NWin):
        WinS = int(i * WinL / 2)
        WinE = min(WinS + WinL, FN)
        RGB_win = RGB[WinS:WinE, :]
        if RGB_win.shape[0] < 2: continue
        RGBBase = np.mean(RGB_win, axis=0)
        if np.any(RGBBase == 0): continue
        RGBNorm = RGB_win / RGBBase
        Xs = 3 * RGBNorm[:, 0] - 2 * RGBNorm[:, 1]
        Ys = 1.5 * RGBNorm[:, 0] + RGBNorm[:, 1] - 1.5 * RGBNorm[:, 2]
        min_signal_length = 3 * 2 * 2
        if len(Xs) <= min_signal_length:
            continue
        try:
            Xf = signal.filtfilt(B, A, Xs)
            Yf = signal.filtfilt(B, A, Ys)
        except Exception:
            continue
        std_Xf = np.std(Xf)
        std_Yf = np.std(Yf)
        if std_Yf == 0: continue
        Alpha = std_Xf / std_Yf
        SWin = Xf - Alpha * Yf
        hann_win = signal.windows.hann(len(SWin))
        SWin_hann = SWin * hann_win
        WinM = WinS + (WinE - WinS) // 2
        len1 = min(len(SWin_hann)//2, WinM - WinS)
        len2 = min(len(SWin_hann) - len1, WinE - WinM)
        if len1 > 0:
            S[WinS : WinS + len1] += SWin_hann[:len1]
        if len2 > 0:
            S[WinM : WinM + len2] += SWin_hann[len1 : len1+len2]
    return S

def extract_heart_rate(BVP_signal, FS):
    min_peak_dist = FS * (60.0 / 180.0)
    peaks, _ = signal.find_peaks(BVP_signal, distance=min_peak_dist, prominence=np.std(BVP_signal)*0.1)
    if len(peaks) < 2:
        return None, None
    peak_intervals_sec = np.diff(peaks) / FS
    valid_intervals = peak_intervals_sec[(peak_intervals_sec >= 60.0/180.0) & (peak_intervals_sec <= 60.0/40.0)]
    if len(valid_intervals) < 1:
        return None, None
    avg_ibi = np.mean(valid_intervals)
    heart_rate_bpm = 60.0 / avg_ibi
    return heart_rate_bpm, peaks
