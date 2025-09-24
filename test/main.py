from deepface import DeepFace
import cv2

cap = cv2.VideoCapture(0)

print("⚡ Đang load database ảnh trong folder images/...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    try:
        result = DeepFace.find(frame, db_path="images", enforce_detection=False)

        if len(result) > 0:
            best_match = result[0].iloc[0]["identity"]
            name = best_match.split("\\")[-1].split(".")[0]
            cv2.putText(frame, f"Phát hiện: {name}",
                        (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Không nhận diện được",
                        (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 0, 255), 2)

    except Exception as e:
        print("Lỗi:", e)

    cv2.imshow("Face Recognition", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()