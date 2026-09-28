# Hindsight documentation

Place the Hindsight documentation provided by the human in this directory
(`docs/hindsight/`).

The implementation follows the official `hindsight-client` API:

```python
from hindsight_client import Hindsight

client = Hindsight(base_url="http://localhost:8888")  # from HINDSIGHT_API_URL
client.retain(bank_id="review-payments-service", content="...")
response = client.recall(bank_id="review-payments-service", query="...")
texts = [r.text for r in response.results]
```

One bank per project (`review-payments-service`, `review-web-app`); banks are
auto-created on first retain. See `hindsight-client` 0.10.x for details.
