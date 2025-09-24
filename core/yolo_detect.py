import cv2
import numpy as np

INPUT_SIZE = 416
CONF_THRESHOLD = 0.5
NMS_THRESHOLD = 0.4

def init_yolo(weights_path, cfg_path, names_path):
    try:
        net = cv2.dnn.readNet(weights_path, cfg_path)
        with open(names_path, "r") as f:
            classes = [line.strip() for line in f.readlines()]
        output_layers = [layer for layer in net.getLayerNames() if layer.startswith("yolo")]
        print("✓ YOLO loaded")
        return net, classes, output_layers
    except Exception as e:
        print(f"✗ YOLO load error: {e}")
        return None, [], []

def detect_objects(frame, net, output_layers, classes):
    blob = cv2.dnn.blobFromImage(frame, 1/255, (INPUT_SIZE, INPUT_SIZE), (0, 0, 0), True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)

    boxes, confidences, class_ids = [], [], []
    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > CONF_THRESHOLD:
                w, h = int(detection[2] * frame.shape[1]), int(detection[3] * frame.shape[0])
                x, y = int(detection[0] * frame.shape[1] - w / 2), int(detection[1] * frame.shape[0] - h / 2)
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD)
    return indices, boxes, confidences, class_ids