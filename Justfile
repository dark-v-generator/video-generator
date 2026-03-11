# Justfile for video-generator

# Generate a two part reddit video
generate-reddit url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}}

# Generate a two part reddit video in low quality (fast)
generate-reddit-fast url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}} --low-quality

# Format code
fmt:
    .venv/bin/black src scripts tests
