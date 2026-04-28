# Co-Pilot Worker

The worker owns background jobs:

- scheduled patient prefetch
- on-demand patient reindex
- document chunking
- embedding writes
- verified relationship extraction

The first implementation should use the same Python settings contract as the API and run as a separate Railway service.
