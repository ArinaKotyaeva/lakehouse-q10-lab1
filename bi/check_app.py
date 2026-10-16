import json
from pathlib import Path
from streamlit.testing.v1 import AppTest
at=AppTest.from_file('/app/app.py',default_timeout=180).run()
assert not at.exception and not at.error, (at.exception,at.error)
assert len(at.dataframe)>=2
observed={}
for name in ['customer','orders','lineitem','nation']:
    at.selectbox[0].set_value(name).run(timeout=180)
    assert not at.exception and not at.error
    df=at.dataframe[0].value
    assert len(df)==(25 if name=='nation' else 100)
    observed[name]={'rows_shown':len(df),'columns':list(df.columns)}
assert len(at.dataframe[1].value)==25
at.radio[0].set_value('Gold').run(timeout=180)
assert not at.exception and not at.error
assert len(at.dataframe[0].value)==20
result={'bronze':observed,'nation_aggregate_rows':25,'gold_rows':20,'ui_errors':0}
Path('/results/bi_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
