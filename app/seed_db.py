
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