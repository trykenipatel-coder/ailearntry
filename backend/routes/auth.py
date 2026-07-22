from flask import Blueprint, request, jsonify, session
from database import get_db, generate_student_code
import hashlib

auth_bp = Blueprint("auth", __name__)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ─── SQLITE AUTH (existing) ──────────────────────────────────────────

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    role = data.get("role", "student").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    db = get_db()
    user = None

    if role == "student":
        user = db.execute(
            "SELECT * FROM students WHERE email = ? AND password = ?",
            (email, hash_password(password)),
        ).fetchone()
    elif role == "mentor":
        user = db.execute(
            "SELECT * FROM mentors WHERE email = ? AND password = ?",
            (email, hash_password(password)),
        ).fetchone()
    elif role == "admin":
        user = db.execute(
            "SELECT * FROM admins WHERE email = ? AND password = ?",
            (email, hash_password(password)),
        ).fetchone()

    db.close()

    if user:
        u = dict(user)

        # Check mentor status before allowing login
        if role == "mentor":
            status = u.get("status", "active")
            if status == "pending":
                db.close()
                return jsonify({
                    "success": False,
                    "message": "Your account is under admin review. You will be able to log in after approval.",
                    "status": "pending",
                }), 403
            elif status == "rejected":
                db.close()
                return jsonify({
                    "success": False,
                    "message": "Your registration was rejected by admin. Contact support.",
                    "status": "rejected",
                }), 403
            elif status == "suspended":
                db.close()
                return jsonify({
                    "success": False,
                    "message": "Your account has been disabled by admin. Contact support.",
                    "status": "suspended",
                }), 403

        session["user_id"] = u.get("student_id") or u.get("mentor_id") or u.get("admin_id")
        session["email"] = u["email"]
        session["role"] = role
        session["name"] = u.get("name") or u.get("mentor_name") or "Admin"

        return jsonify({
            "success": True,
            "message": f"Welcome {session['name']}!",
            "role": role,
            "user": {
                "id": session["user_id"],
                "name": session["name"],
                "email": u["email"],
            },
        })

    return jsonify({"success": False, "message": "Invalid credentials"}), 401


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    role = data.get("role", "student").strip()
    course = data.get("course", "").strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields required"}), 400

    db = get_db()
    try:
        if role == "student":
            code = generate_student_code(db)
            db.execute(
                "INSERT INTO students (name, email, password, course, student_code) VALUES (?, ?, ?, ?, ?)",
                (name, email, hash_password(password), course, code),
            )
        elif role == "mentor":
            subject = data.get("subject", "").strip()
            db.execute(
                "INSERT INTO mentors (mentor_name, email, password, subject, status) VALUES (?, ?, ?, ?, 'pending')",
                (name, email, hash_password(password), subject),
            )
        db.commit()

        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        session["user_id"] = user_id
        session["email"] = email
        session["role"] = role
        session["name"] = name

        msg = "Registration successful!"
        if role == "mentor":
            msg = "Registration submitted! Your account is under admin review. You will be able to log in after approval."

        # Sync to Firebase
        try:
            from backend.services.firebase_service import create_user as fb_create
            fb_create(str(user_id), name, email, role)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": msg,
            "role": role,
            "pendingApproval": role == "mentor",
        })
    except Exception:
        return jsonify({"success": False, "message": "Email already exists"}), 409
    finally:
        db.close()


# ─── FIREBASE AUTH ───────────────────────────────────────────────────

@auth_bp.route("/api/auth/firebase/login", methods=["POST"])
def firebase_login():
    from backend.services.firebase_service import verify_firebase_token, get_user

    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "message": "Token required"}), 400

    decoded = verify_firebase_token(id_token)
    if not decoded:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    uid = decoded.get("uid")
    email = decoded.get("email", "")
    name = decoded.get("name", decoded.get("displayName", "User"))

    # Check if user exists in Firestore
    fb_user = get_user(uid)
    if not fb_user:
        return jsonify({
            "success": False,
            "message": "User not registered. Please sign up first.",
            "registerRequired": True,
        }), 404

    role = fb_user.get("role", "student")

    # Ensure local SQLite user exists
    db = get_db()
    local_user = db.execute(
        "SELECT * FROM students WHERE email = ?", (email,)
    ).fetchone()
    if not local_user:
        placeholder_pw = hashlib.sha256(f"fb_{uid}".encode()).hexdigest()
        if role == "student":
            code = generate_student_code(db)
            db.execute("INSERT INTO students (name, email, password, student_code) VALUES (?, ?, ?, ?)",
                       (fb_user.get("name", name), email, placeholder_pw, code))
        elif role == "mentor":
            db.execute("INSERT INTO mentors (mentor_name, email, password, status) VALUES (?, ?, ?, 'pending')",
                       (fb_user.get("name", name), email, placeholder_pw))
        db.commit()
        local_user = db.execute(
            "SELECT * FROM students WHERE email = ?", (email,)
        ).fetchone() or db.execute(
            "SELECT * FROM mentors WHERE email = ?", (email,)
        ).fetchone()
    db.close()

    # Check mentor status for Firebase login
    if role == "mentor" and local_user:
        status = local_user.get("status", "active")
        if status in ("pending", "rejected", "suspended"):
            messages = {
                "pending": "Your account is under admin review. You will be able to log in after approval.",
                "rejected": "Your registration was rejected by admin. Contact support.",
                "suspended": "Your account has been disabled by admin. Contact support.",
            }
            return jsonify({
                "success": False,
                "message": messages[status],
                "status": status,
            }), 403

    local_id = local_user.get("student_id") or local_user.get("mentor_id")
    session["user_id"] = local_id if local_id else uid
    session["email"] = email
    session["role"] = role
    session["name"] = fb_user.get("name", name)
    session["firebase_uid"] = uid

    return jsonify({
        "success": True,
        "message": f"Welcome {session['name']}!",
        "role": role,
        "user": {
            "id": session["user_id"],
            "name": session["name"],
            "email": email,
        },
    })


@auth_bp.route("/api/auth/firebase/register", methods=["POST"])
def firebase_register():
    from backend.services.firebase_service import verify_firebase_token, create_user as fb_create_user

    data = request.get_json()
    id_token = data.get("idToken")
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "student").strip()

    if not id_token:
        return jsonify({"success": False, "message": "Token required"}), 400

    decoded = verify_firebase_token(id_token)
    if not decoded:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    uid = decoded.get("uid")
    fb_email = decoded.get("email", email)
    fb_name = decoded.get("name", decoded.get("displayName", name))

    # Create Firestore user document
    fb_create_user(uid, fb_name, fb_email, role)

    # Create local SQLite user for compatibility
    db = get_db()
    placeholder_pw = hashlib.sha256(f"fb_{uid}".encode()).hexdigest()
    if role == "student":
        code = generate_student_code(db)
        db.execute("INSERT OR IGNORE INTO students (name, email, password, student_code) VALUES (?, ?, ?, ?)",
                   (fb_name, fb_email, placeholder_pw, code))
    elif role == "mentor":
        db.execute("INSERT OR IGNORE INTO mentors (mentor_name, email, password) VALUES (?, ?, ?)",
                   (fb_name, fb_email, placeholder_pw))
    db.commit()
    local_user = db.execute(
        "SELECT * FROM students WHERE email = ?", (fb_email,)
    ).fetchone() or db.execute(
        "SELECT * FROM mentors WHERE email = ?", (fb_email,)
    ).fetchone()
    db.close()

    local_id = local_user.get("student_id") or local_user.get("mentor_id") if local_user else None
    session["user_id"] = local_id if local_id else uid
    session["email"] = fb_email
    session["role"] = role
    session["name"] = fb_name
    session["firebase_uid"] = uid

    return jsonify({
        "success": True,
        "message": f"Welcome {fb_name}!",
        "role": role,
    })


@auth_bp.route("/api/auth/firebase/google", methods=["POST"])
def firebase_google():
    from backend.services.firebase_service import verify_firebase_token, get_user, create_user as fb_create_user

    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "message": "Token required"}), 400

    decoded = verify_firebase_token(id_token)
    if not decoded:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    uid = decoded.get("uid")
    email = decoded.get("email", "")
    name = decoded.get("name", decoded.get("displayName", "Google User"))

    fb_user = get_user(uid)
    if fb_user:
        role = fb_user.get("role", "student")
    else:
        fb_create_user(uid, name, email, "student")
        role = "student"

    db = get_db()
    placeholder_pw = hashlib.sha256(f"fb_{uid}".encode()).hexdigest()
    existing = db.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
    if not existing:
        code = generate_student_code(db)
        db.execute("INSERT INTO students (name, email, password, student_code) VALUES (?, ?, ?, ?)",
                   (name, email, placeholder_pw, code))
        db.commit()
        existing = db.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
    db.close()

    local_id = existing["student_id"] if existing else None
    session["user_id"] = local_id if local_id else uid
    session["email"] = email
    session["role"] = role
    session["name"] = name
    session["firebase_uid"] = uid

    return jsonify({
        "success": True,
        "message": f"Welcome {name}!",
        "role": role,
    })


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out"})
