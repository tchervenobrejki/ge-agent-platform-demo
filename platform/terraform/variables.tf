variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west3"
}

variable "enable_console_eval" {
  description = "Create the output bucket for Agent Evaluation runs in the console (optional, see docs/evaluation.md)"
  type        = bool
  default     = false
}
