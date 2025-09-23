import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("config/key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def update_user_field(examId, studentId, fields: dict):
    try:
        db.collection("exams").document(examId).collection("users").document(studentId).update(fields)
    except Exception as e:
        print(f"[Firebase Error] {e}")

def get_user_doc(examId, studentId):
    return db.collection("exams").document(examId).collection("users").document(studentId).get()
