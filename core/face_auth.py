from deepface import DeepFace

def verify_face(frame, reference_path):
    try:
        result = DeepFace.verify(
            img1_path=frame,
            img2_path=reference_path,
            model_name="ArcFace",
            enforce_detection=False
        )
        return result.get("verified", False)
    except Exception as e:
        print(f"DeepFace error: {e}")
        return None
