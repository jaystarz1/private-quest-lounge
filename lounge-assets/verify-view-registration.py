"""Read-only landmark registration gate for the north day/dusk/night assets.

Matches photograph features below the horizon, robustly fits an affine map,
and rejects a mirrored, rotated, shifted, or recropped night viewpoint.
Usage: python3 lounge-assets/verify-view-registration.py
"""
from pathlib import Path
import cv2
import numpy as np

root = Path(__file__).resolve().parent / "views-src"
size = (1933, 814)
day = cv2.resize(cv2.imread(str(root / "day-north-a46.jpg"), cv2.IMREAD_GRAYSCALE), size)
detector = cv2.SIFT_create(nfeatures=12000, contrastThreshold=0.015)
equalize = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(12, 8))
mask = np.zeros(day.shape, np.uint8)
mask[330:] = 255  # Architecture and park, not changing clouds/lighting.
reference = day
reference_name = "day"
accumulated = np.eye(3)
for name in ("dusk", "night"):
    # Adjacent lighting exposures preserve far more SIFT features than a
    # direct daylight/near-black match. Compose the two verified transforms.
    keys, descriptors = detector.detectAndCompute(equalize.apply(reference), mask)
    target = cv2.resize(cv2.imread(str(root / "aligned" / f"{name}-north-a46.png"), cv2.IMREAD_GRAYSCALE), size)
    target_keys, target_desc = detector.detectAndCompute(equalize.apply(target), mask)
    matches = cv2.BFMatcher().knnMatch(descriptors, target_desc, k=2)
    good = [a for a, b in matches if a.distance < 0.72 * b.distance]
    assert len(good) >= 20, f"{name}: insufficient matched landmarks"
    source_pts = np.float32([keys[m.queryIdx].pt for m in good])
    target_pts = np.float32([target_keys[m.trainIdx].pt for m in good])
    matrix, inliers = cv2.estimateAffinePartial2D(source_pts, target_pts, method=cv2.RANSAC, ransacReprojThreshold=3)
    assert matrix is not None
    errors = np.linalg.norm(target_pts - source_pts, axis=1)[inliers.ravel() == 1]
    count = int(inliers.sum())
    shift = float(np.linalg.norm(matrix[:, 2]))
    scale = float(np.linalg.norm(matrix[:, 0]))
    angle = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    print(f"{reference_name}->{name}: {count} inlier landmarks; median offset {np.median(errors):.2f}px; "
          f"shift {shift:.2f}px; scale {scale:.5f}; rotation {angle:.3f}deg")
    assert count >= 20 and shift < 10 and abs(scale - 1) < 0.01 and abs(angle) < 0.3, f"{name}: viewpoint mismatch"
    assert np.median(errors) < 5, f"{name}: landmarks do not register"
    matched = source_pts[inliers.ravel() == 1]
    spread = np.ptp(matched, axis=0)
    print(f"  landmark coverage: {spread[0]:.0f}px horizontally, {spread[1]:.0f}px vertically")
    assert spread[0] > size[0] * 0.5 and spread[1] > size[1] * 0.2, "Matches confined to one small feature"
    accumulated = np.vstack([matrix, [0, 0, 1]]) @ accumulated
    assert np.linalg.norm(accumulated[:2, 2]) < 10, "Combined night/day offset too large"
    reference, reference_name = target, name
