"""Script to run the Xuan-Flow Gateway API."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("xuan_flow.api.app:app", host="0.0.0.0", port=8000, reload=True)
