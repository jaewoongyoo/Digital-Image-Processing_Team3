import cv2
from vision.image_processing import process


def track(frame, lower, upper, min_area=500):
    raw, mask = process(frame, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    point = None
    if contours:
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) >= min_area:
            moments = cv2.moments(contour)
            if moments["m00"]:
                point = (int(moments["m10"] / moments["m00"]), int(moments["m01"] / moments["m00"]))
    return point, raw, mask
