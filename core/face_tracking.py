import mediapipe as mp
import cv2
import numpy as np

class FaceTracker:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def process_frame(self, frame):
        results = self.face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        gaze_direction = "UNKNOWN"
        head_pose = "UNKNOWN"

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # Vẽ lưới khuôn mặt
                self.mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles
                    .get_default_face_mesh_tesselation_style())
                self_mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles
                    .get_default_face_mesh_contours_style())
                self.mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_IRISES,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles
                    .get_default_face_mesh_iris_connections_style())

                # Ước tính hướng nhìn và tư thế đầu
                img_h, img_w, img_c = frame.shape
                face_3d = []
                face_2d = []

                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx == 33 or idx == 263 or idx == 1 or idx == 61 or idx == 291 or idx == 199:
                        if idx == 1:
                            nose_2d = (lm.x * img_w, lm.y * img_h)
                            nose_3d = (lm.x * img_w, lm.y * img_h, lm.z * 3000) 

                        x, y = int(lm.x * img_w), int(lm.y * img_h)

                        face_2d.append([x, y])
                        face_3d.append([x, y, lm.z])       
                
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)

                focal_length = 1 * img_w

                cam_matrix = np.array([ [focal_length, 0, img_w / 2],
                                        [0, focal_length, img_h / 2],
                                        [0, 0, 1]])

                dist_matrix = np.zeros((4, 1), dtype=np.float64)

                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)

                rmat, jac = cv2.Rodrigues(rot_vec)

                angles, mtxR, mtxQ, Qx, Qy, Qz = cv2.RQDecomp3x3(rmat)

                x = angles[0] * 360
                y = angles[1] * 360
                z = angles[2] * 360

                if y < -10:
                    head_pose = "Looking Left"
                elif y > 10:
                    head_pose = "Looking Right"
                elif x < -10:
                    head_pose = "Looking Down"
                elif x > 10:
                    head_pose = "Looking Up"
                else:
                    head_pose = "Forward"

                # Để đơn giản, phần phát hiện ánh mắt sẽ chỉ kiểm tra một ngưỡng nhỏ cho tư thế đầu
                # Để có độ chính xác cao hơn, cần phân tích kỹ hơn các điểm landmark của mắt
                if abs(y) < 5 and abs(x) < 5: # Nếu đầu thẳng
                    gaze_direction = "Forward"
                elif y < -5:
                    gaze_direction = "Left"
                elif y > 5:
                    gaze_direction = "Right"
                elif x < -5:
                    gaze_direction = "Down"
                elif x > 5:
                    gaze_direction = "Up"

        return frame, gaze_direction, head_pose

    def __del__(self):
        self.face_mesh.close()
