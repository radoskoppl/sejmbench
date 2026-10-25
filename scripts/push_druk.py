import os
from datasets import Dataset, Features, Value

OUT = "/home/porwat/sejm-dump"
features = Features({
    "term": Value("int64"),
    "number": Value("string"),
    "attachment": Value("string"),
    "pages": Value("int64"),
    "text_len": Value("int64"),
    "error": Value("string"),
    "text": Value("string"),
})
ds = Dataset.from_json(os.path.join(OUT, "druk_texts.jsonl"), features=features)
tok = open(os.path.expanduser("~/.hf-token")).read().strip()
ds.push_to_hub("patrykorwat/sejm-votings", config_name="druk_texts", token=tok)
print("pushed:", len(ds))
