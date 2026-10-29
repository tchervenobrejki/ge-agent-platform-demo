resource "google_project_service" "modelarmor" {
  service            = "modelarmor.googleapis.com"
  disable_on_destroy = false
}
