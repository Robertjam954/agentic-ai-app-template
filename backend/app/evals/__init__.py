"""Local eval runner for the agent loop.

Cases live in the repo-root `evals/` directory. Run `agent-eval` or
`python -m app.evals`.
"""

import warnings

# The template .env ships placeholder secrets. Importing settings always warns
# about them; keep that warning on the server, and keep eval output to the results.
warnings.filterwarnings(
    "ignore",
    message=r'The value of .* is "changethis"',
    category=UserWarning,
)
