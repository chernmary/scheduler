 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/migrations/versions/0004_add_status_to_unique_constraint.py
index 0000000000000000000000000000000000000000..1e812c479b4468a11fc757bfae798e63af72c0be 100644
--- a//dev/null
+++ b/migrations/versions/0004_add_status_to_unique_constraint.py
@@ -0,0 +1,33 @@
+"""add status to shift unique constraint"""
+
+from alembic import op
+import sqlalchemy as sa
+
+revision = "0004_add_status_to_unique_constraint"
+down_revision = "0003_add_status_to_shifts"
+branch_labels = None
+depends_on = None
+
+
+def upgrade():
+    conn = op.get_bind()
+    insp = sa.inspect(conn)
+
+    if "shifts" in insp.get_table_names():
+        with op.batch_alter_table("shifts", recreate="always") as batch:
+            batch.drop_constraint("uix_date_location", type_="unique")
+            batch.create_unique_constraint(
+                "uix_date_location_status", ["date", "location_id", "status"]
+            )
+
+
+def downgrade():
+    conn = op.get_bind()
+    insp = sa.inspect(conn)
+
+    if "shifts" in insp.get_table_names():
+        with op.batch_alter_table("shifts", recreate="always") as batch:
+            batch.drop_constraint("uix_date_location_status", type_="unique")
+            batch.create_unique_constraint(
+                "uix_date_location", ["date", "location_id"]
+            )
 
EOF
)