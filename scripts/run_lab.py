"""Run real TPC-H Q10 ELT and repeatable local benchmark (stdlib only)."""
import argparse, csv, datetime, json, math, random, statistics, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
SQLDIR=ROOT/'sql'; SQLDIR.mkdir(exist_ok=True)
HEADERS={'X-Trino-User':'lab','X-Trino-Source':'lab1-q10','Content-Type':'text/plain'}

def query(sql, label='query'):
    start=time.perf_counter()
    req=urllib.request.Request('http://localhost:18080/v1/statement',data=sql.encode(),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=120) as r: obj=json.load(r)
    rows=[]; cols=[]; qid=obj.get('id')
    while True:
        if 'error' in obj: raise RuntimeError(f"{label}: {obj['error'].get('message')}\n{sql}")
        if 'columns' in obj: cols=[c['name'] for c in obj['columns']]
        rows.extend(obj.get('data',[]))
        if 'nextUri' not in obj: break
        with urllib.request.urlopen(urllib.request.Request(obj['nextUri'],headers=HEADERS),timeout=120) as r: obj=json.load(r)
    elapsed=time.perf_counter()-start
    rec={'label':label,'query_id':qid,'wall_seconds':elapsed,'stats':obj.get('stats',{}),'sql':sql}
    with (OUT/'queries.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    return {'columns':cols,'rows':rows,'seconds':elapsed,'query_id':qid,'stats':obj.get('stats',{})}

def save(name, data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def sqlfile(name,sql): (SQLDIR/name).write_text(sql.strip()+';\n',encoding='utf-8')
def q10(schema):
 return f"""SELECT c.custkey, c.name, sum(l.extendedprice*(1-l.discount)) AS revenue,
c.acctbal, n.name AS nation, c.address, c.phone, c.comment
FROM {schema}.customer c
JOIN {schema}.orders o ON c.custkey=o.custkey
JOIN {schema}.lineitem l ON l.orderkey=o.orderkey
JOIN {schema}.nation n ON c.nationkey=n.nationkey
WHERE o.orderdate >= DATE '1993-10-01' AND o.orderdate < DATE '1994-01-01'
AND l.returnflag='R'
GROUP BY c.custkey,c.name,c.acctbal,n.name,c.address,c.phone,c.comment
ORDER BY revenue DESC, c.custkey LIMIT 20"""
COLS={'customer':'custkey, name, acctbal, nationkey, address, phone, comment',
      'orders':'orderkey, custkey, orderdate',
      'lineitem':'orderkey, linenumber, extendedprice, discount, returnflag',
      'nation':'nationkey, name'}
VARIANTS=[('bronze_gzip','PARQUET','GZIP'),('bronze','PARQUET','ZSTD'),('bronze_orc','ORC','ZSTD'),('bronze_none','PARQUET','NONE')]

def stats(schema,table):
 r=query(f'SELECT count(*) FROM lakehouse.{schema}.{table}','count')
 files=query(f'SELECT count(*),coalesce(sum(file_size_in_bytes),0) FROM lakehouse.{schema}."{table}$files"','files')
 return {'table':f'{schema}.{table}','rows':r['rows'][0][0],'data_files':files['rows'][0][0],'bytes':files['rows'][0][1]}

def equivalent(expected, actual):
 assert expected['columns']==actual['columns'],(expected['columns'],actual['columns'])
 assert len(expected['rows'])==len(actual['rows'])==20
 for a,b in zip(expected['rows'],actual['rows']):
  for i,(x,y) in enumerate(zip(a,b)):
   if isinstance(x,float) or isinstance(y,float): assert math.isclose(float(x),float(y),rel_tol=1e-10,abs_tol=1e-6),(i,x,y)
   else: assert x==y,(i,x,y)

def run(args):
 previous=json.loads((OUT/'environment.json').read_text()) if (OUT/'environment.json').exists() else {}
 if previous.get('scale',args.scale)!=args.scale: raise RuntimeError('Scale differs from existing results; use a separate Compose project and empty results directory')
 print('Waiting for Trino...',flush=True)
 for attempt in range(90):
  try: query('SELECT 1','readiness'); break
  except Exception:
   if attempt==89: raise
   time.sleep(2)
 env={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scale':args.scale,'repeats':args.repeats,'version':query('SELECT version()')['rows'][0][0]}
 save('environment.json',env)
 baseline=query(q10('tpch.'+args.scale),'reference'); save('reference.json',baseline); sqlfile('01_reference.sql',q10('tpch.'+args.scale))
 metrics=[]; writes=[]
 old_writes=json.loads((OUT/'writes.json').read_text()) if (OUT/'writes.json').exists() else []
 for schema,fmt,codec in VARIANTS:
  query(f'CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}')
  for table,columns in COLS.items():
   create=f"CREATE TABLE IF NOT EXISTS lakehouse.{schema}.{table} WITH (format='{fmt}',compression_codec='{codec}') AS SELECT {columns} FROM tpch.{args.scale}.{table}"
   sqlfile(f'02_{schema}_{table}.sql',create)
   exists=query(f"SELECT count(*) FROM lakehouse.information_schema.tables WHERE table_schema='{schema}' AND table_name='{table}'")['rows'][0][0]
   if exists:
    print(f'Reusing {schema}.{table}; original write time retained',flush=True)
    old=old_writes
    matching=[x for x in old if x['table']==schema+'.'+table]
    if not matching: raise RuntimeError('Existing table without write measurement: use a fresh project or retain results/writes.json')
    writes.append(matching[0])
   else:
    r=query(create,'write_'+schema+'_'+table)
    writes.append({'table':schema+'.'+table,'format':fmt,'codec':codec,'seconds':r['seconds'],'query_id':r['query_id']})
   save('writes.json',writes)
   m=stats(schema,table); m.update(format=fmt,codec=codec,columns=columns); metrics.append(m); save('table_metrics.json',metrics)
   print(f"{schema}.{table}: {m['rows']:,} rows, {m['bytes']/1e6:.2f} MB",flush=True)
  equivalent(baseline,query(q10('lakehouse.'+schema),'check_'+schema))
  sqlfile('03_q10_'+schema+'.sql',q10('lakehouse.'+schema))
 # Sequential warm-up per layout, followed by interleaved measured rounds.
 for schema,_,_ in VARIANTS: query(q10('lakehouse.'+schema),'warmup_'+schema)
 runs=[]; rng=random.Random(20261016)
 for repetition in range(args.repeats):
  order=list(VARIANTS); rng.shuffle(order)
  for schema,fmt,codec in order:
   r=query(q10('lakehouse.'+schema),'benchmark_'+schema); equivalent(baseline,r)
   runs.append({'schema':schema,'format':fmt,'codec':codec,'round':repetition+1,'seconds':r['seconds'],'query_id':r['query_id'],'server_elapsed_ms':r['stats'].get('elapsedTimeMillis'),'processed_bytes':r['stats'].get('processedBytes')})
   save('benchmark_runs.json',runs)
   print(f"Round {repetition+1}: {schema} {r['seconds']:.3f}s",flush=True)
 bench=[]
 for schema,fmt,codec in VARIANTS:
  times=[x['seconds'] for x in runs if x['schema']==schema]
  bench.append({'schema':schema,'format':fmt,'codec':codec,'bytes':sum(x['bytes'] for x in metrics if x['table'].startswith(schema+'.')),'write_seconds':sum(x['seconds'] for x in writes if x['table'].startswith(schema+'.')),'median_seconds':statistics.median(times),'min_seconds':min(times),'max_seconds':max(times),'runs':len(times)})
 save('benchmark.json',bench)
 with (OUT/'benchmark.csv').open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.DictWriter(f,fieldnames=list(bench[0])); writer.writeheader(); writer.writerows(bench)
 query('CREATE SCHEMA IF NOT EXISTS lakehouse.silver'); query('CREATE SCHEMA IF NOT EXISTS lakehouse.gold')
 transformations=[('04_silver_customers.sql',"""CREATE TABLE IF NOT EXISTS lakehouse.silver.customer_dim
WITH (format='PARQUET',compression_codec='ZSTD') AS
SELECT c.custkey,c.name,c.acctbal,n.name AS nation,
c.address,c.phone,c.comment,trim(c.name) AS name_normalized,
trim(c.address) AS address_normalized,trim(c.comment) AS comment_normalized
FROM lakehouse.bronze.customer c JOIN lakehouse.bronze.nation n ON c.nationkey=n.nationkey
WHERE c.custkey IS NOT NULL"""),
 ('05_silver_returns.sql',"""CREATE TABLE IF NOT EXISTS lakehouse.silver.returned_lines
WITH (format='PARQUET',compression_codec='ZSTD') AS
SELECT o.custkey,o.orderkey,l.linenumber,o.orderdate,
l.extendedprice,l.discount,l.extendedprice*(1-l.discount) AS revenue
FROM lakehouse.bronze.orders o JOIN lakehouse.bronze.lineitem l ON l.orderkey=o.orderkey
WHERE o.orderdate >= DATE '1993-10-01' AND o.orderdate < DATE '1994-01-01'
AND upper(trim(l.returnflag))='R'
AND l.extendedprice >= 0 AND l.discount BETWEEN 0 AND 1"""),
 ('06_gold.sql',"""CREATE TABLE IF NOT EXISTS lakehouse.gold.returned_customers_top20
WITH (format='PARQUET',compression_codec='ZSTD') AS
SELECT c.custkey,c.name,sum(l.revenue) AS revenue,c.acctbal,c.nation,c.address,c.phone,c.comment
FROM lakehouse.silver.customer_dim c JOIN lakehouse.silver.returned_lines l ON c.custkey=l.custkey
GROUP BY c.custkey,c.name,c.acctbal,c.nation,c.address,c.phone,c.comment
ORDER BY revenue DESC,c.custkey LIMIT 20""")]
 for name,sql in transformations: sqlfile(name,sql); query(sql,name)
 gold=query('SELECT * FROM lakehouse.gold.returned_customers_top20 ORDER BY revenue DESC,custkey','gold_result')
 equivalent(baseline,gold); save('gold_top20.json',gold)
 with (OUT/'gold_top20.csv').open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.writer(f); writer.writerow(gold['columns']); writer.writerows(gold['rows'])
 for schema,table in [('silver','customer_dim'),('silver','returned_lines'),('gold','returned_customers_top20')]:
  m=stats(schema,table); m.update(format='PARQUET',codec='ZSTD'); metrics.append(m)
 save('table_metrics.json',metrics)
 checks={}
 checksql={
 'customer_duplicates':'SELECT count(*)-count(DISTINCT custkey) FROM lakehouse.bronze.customer',
 'order_duplicates':'SELECT count(*)-count(DISTINCT orderkey) FROM lakehouse.bronze.orders',
 'line_duplicates':'SELECT count(*) FROM (SELECT orderkey,linenumber FROM lakehouse.bronze.lineitem GROUP BY 1,2 HAVING count(*)>1)',
 'invalid_money':'SELECT count(*) FROM lakehouse.bronze.lineitem WHERE extendedprice IS NULL OR extendedprice<0 OR discount IS NULL OR discount NOT BETWEEN 0 AND 1',
 'orphan_orders':'SELECT count(*) FROM lakehouse.bronze.orders o LEFT JOIN lakehouse.bronze.customer c ON o.custkey=c.custkey WHERE c.custkey IS NULL',
 'orphan_lines':'SELECT count(*) FROM lakehouse.bronze.lineitem l LEFT JOIN lakehouse.bronze.orders o ON o.orderkey=l.orderkey WHERE o.orderkey IS NULL',
 'orphan_nations':'SELECT count(*) FROM lakehouse.bronze.customer c LEFT JOIN lakehouse.bronze.nation n ON n.nationkey=c.nationkey WHERE n.nationkey IS NULL'}
 for label,sql in checksql.items():
  checks[label]=query(sql,label)['rows'][0][0]; assert checks[label]==0,(label,checks[label])
 sqlfile('07_quality.sql',';\n\n'.join(checksql.values()))
 checks['gold_matches_tpch']=True; checks['all_bronze_variants_match_tpch']=True; save('checks.json',checks)
 # Separate demo table avoids changing the production Gold/Silver data.
 query("CREATE TABLE IF NOT EXISTS lakehouse.silver.evolution_demo WITH (format='PARQUET',compression_codec='ZSTD') AS SELECT custkey,name FROM lakehouse.silver.customer_dim LIMIT 3")
 before=query('SELECT * FROM lakehouse.silver.evolution_demo')
 columns=before['columns']
 evolution_sql=[]
 if 'source' not in columns and 'data_source' not in columns:
  evolution_sql.append('ALTER TABLE lakehouse.silver.evolution_demo ADD COLUMN source VARCHAR'); query(evolution_sql[-1])
  evolution_sql.append('ALTER TABLE lakehouse.silver.evolution_demo RENAME COLUMN source TO data_source'); query(evolution_sql[-1])
 after=query('SELECT * FROM lakehouse.silver.evolution_demo')
 assert len(before['rows'])==len(after['rows'])==3
 assert 'data_source' in after['columns']
 save('schema_evolution.json',{'before':before,'after':after}); sqlfile('08_schema_evolution.sql',';\n'.join(evolution_sql) or 'SELECT * FROM lakehouse.silver.evolution_demo')
 snapshot=query('SELECT snapshot_id FROM lakehouse.silver."evolution_demo$snapshots" ORDER BY committed_at DESC LIMIT 1')['rows'][0][0]
 old_count=query('SELECT count(*) FROM lakehouse.silver.evolution_demo')['rows'][0][0]
 insert="INSERT INTO lakehouse.silver.evolution_demo VALUES (-1,'temporary row','demo')"; query(insert)
 new_count=query('SELECT count(*) FROM lakehouse.silver.evolution_demo')['rows'][0][0]
 travel=f'SELECT count(*) FROM lakehouse.silver.evolution_demo FOR VERSION AS OF {snapshot}'
 historical=query(travel)['rows'][0][0]
 rollback=f'ALTER TABLE lakehouse.silver.evolution_demo EXECUTE rollback_to_snapshot({snapshot})'; query(rollback)
 restored=query('SELECT count(*) FROM lakehouse.silver.evolution_demo')['rows'][0][0]
 assert (old_count,new_count,historical,restored)==(3,4,3,3)
 save('time_travel.json',{'snapshot_id':snapshot,'before':old_count,'after_insert':new_count,'historical':historical,'restored':restored})
 sqlfile('09_time_travel.sql',f'-- Snapshot from this run; discover the current ID before repeating.\n{insert};\n{travel};\n{rollback}')
 env['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save('environment.json',env)
 print('SUCCESS: all layouts, Gold, quality checks, schema evolution and rollback verified.',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(); parser.add_argument('--scale',default='sf1',choices=['tiny','sf1','sf10']); parser.add_argument('--repeats',type=int,default=5)
 args=parser.parse_args()
 if args.repeats<3: parser.error('At least three measured repeats required')
 run(args)
