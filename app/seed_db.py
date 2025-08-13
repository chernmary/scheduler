 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/app/seed_db.py
index 0000000000000000000000000000000000000000..c32e3c631bf2a95c8aaa5325b83a046649bd9163 100644
--- a//dev/null
+++ b/app/seed_db.py
@@ -0,0 +1,13 @@
+from app.seed_locations import seed_locations
+from app.seed_employees import seed_employees
+from app.seed_employee_settings import seed_employee_settings
+
+
+def seed_all():
+    seed_locations()
+    seed_employees()
+    seed_employee_settings()
+
+
+if __name__ == "__main__":
+    seed_all()
 
EOF
)