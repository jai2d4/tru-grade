"""Shared analysis-job queue and the worker that drains it.

`store` is safe to import anywhere (it touches only Postgres). `worker`
defers every heavy CV import until a job actually runs, so importing it
from the web service or a test does not load torch.
"""
