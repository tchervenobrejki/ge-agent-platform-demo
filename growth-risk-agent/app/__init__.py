# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from dotenv import load_dotenv

# Load .env before importing the agent: tool modules read their configuration
# (RAG corpora, MCP caller SA, BigQuery Analytics project) at import time, and
# `from app.app_utils import ...` in fast_api_app.py imports this package --
# and therefore the agent -- before fast_api_app's own load_dotenv() runs.
# No-op when deployed: .env is not shipped, real env vars come from Terraform.
load_dotenv()

# gcsfs first asks the Storage Control API for the bucket layout; under Agent
# Identity that gRPC call gets a 401 and gcsfs falls back to the standard GCS
# client (uploads succeed). It logs a WARNING on every upload -- hundreds per
# run -- which buries real errors, so keep only its errors.
logging.getLogger("gcsfs").setLevel(logging.ERROR)

from .agent import app  # noqa: E402

__all__ = ["app"]
