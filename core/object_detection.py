import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

# A wrapper class to handle MediaPipe object detection
class ObjectDetector:
    def __init__(self, model_path='config/efficientdet_lite0.tflite', max_results=5, score_threshold=0.5):
        """
        Initializes the MediaPipe Object Detector.
        
        Args:
            model_path (str): Path to the TFLite model file.
            max_results (int): The maximum number of objects to detect.
            score_threshold (float): The minimum confidence score for a detection to be considered valid.
        """
        try:
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.ObjectDetectorOptions(
                base_options=base_options,
                max_results=max_results,
                score_threshold=score_threshold
            )
            self.detector = vision.ObjectDetector.create_from_options(options)
            print("✓ MediaPipe Object Detector loaded")
        except Exception as e:
            print(f"✗ MediaPipe load error: {e}")
            self.detector = None

    def detect(self, frame):
        """
        Performs object detection on a single frame.
        
        Args:
            frame: The input image frame from OpenCV (in BGR format).
            
        Returns:
            A list of detections. Each detection is a dictionary containing 'label', 'score', and 'bbox'.
            Returns an empty list if initialization failed or no objects are detected.
        """
        if not self.detector:
            return []

        # Convert the frame from BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create a MediaPipe Image object
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Perform detection
        detection_result = self.detector.detect(mp_image)
        
        detections = []
        for detection in detection_result.detections:
            category = detection.categories[0]
            label = category.category_name
            score = category.score
            
            bbox = detection.bounding_box
            # Convert bbox to a format that's easier to use with OpenCV: (x, y, w, h)
            cv2_bbox = (bbox.origin_x, bbox.origin_y, bbox.width, bbox.height)
            
            detections.append({'label': label, 'score': score, 'bbox': cv2_bbox})
            
        return detections
