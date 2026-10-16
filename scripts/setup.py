import json, time, urllib.request, urllib.error, hashlib, hmac, datetime

def request(url, data=None, method=None, headers=None):
    req=urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, method=method, headers=headers or {"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode()
# Create the S3 bucket using an AWS Signature V4 signed PUT, without extra dependencies.
def bucket():
    now=datetime.datetime.now(datetime.timezone.utc); stamp=now.strftime('%Y%m%dT%H%M%SZ'); day=now.strftime('%Y%m%d')
    host='localhost:19000'; path='/lakehouse'; payload=hashlib.sha256(b'').hexdigest()
    headers=f'host:{host}\nx-amz-content-sha256:{payload}\nx-amz-date:{stamp}\n'
    signed='host;x-amz-content-sha256;x-amz-date'
    canonical=f'PUT\n{path}\n\n{headers}\n{signed}\n{payload}'
    scope=f'{day}/us-east-1/s3/aws4_request'; msg=f'AWS4-HMAC-SHA256\n{stamp}\n{scope}\n'+hashlib.sha256(canonical.encode()).hexdigest()
    def hm(key,value): return hmac.new(key,value.encode(),hashlib.sha256).digest()
    key=hm(hm(hm(hm(b'AWS4lab_local_password',day),'us-east-1'),'s3'),'aws4_request')
    signature=hmac.new(key,msg.encode(),hashlib.sha256).hexdigest()
    auth=f'AWS4-HMAC-SHA256 Credential=labadmin/{scope}, SignedHeaders={signed}, Signature={signature}'
    req=urllib.request.Request('http://'+host+path,data=b'',method='PUT',headers={'x-amz-date':stamp,'x-amz-content-sha256':payload,'Authorization':auth})
    try:
        with urllib.request.urlopen(req,timeout=30) as r: print('Bucket:',r.status)
    except urllib.error.HTTPError as e:
        body=e.read().decode()
        if e.code!=409 or 'BucketAlreadyOwnedByYou' not in body: raise RuntimeError(body)

if __name__=='__main__':
    for attempt in range(60):
        try:
            request('http://localhost:18181/health'); break
        except Exception: time.sleep(2)
    bucket()
    try: print(request('http://localhost:18181/management/v1/bootstrap',{'accept-terms-of-use':True}))
    except urllib.error.HTTPError as e:
        if e.code!=400 and e.code!=409: raise
        print('Bootstrap:',e.read().decode())
    warehouses=json.loads(request('http://localhost:18181/management/v1/warehouse?project-id=00000000-0000-0000-0000-000000000000'))
    if not any(w.get('name',w.get('warehouse-name'))=='lab1' for w in warehouses.get('warehouses',[])):
        print(request('http://localhost:18181/management/v1/warehouse',{'warehouse-name':'lab1','project-id':'00000000-0000-0000-0000-000000000000','storage-profile':{'type':'s3','bucket':'lakehouse','key-prefix':'lab1','endpoint':'http://minio:9000','region':'us-east-1','path-style-access':True,'flavor':'s3-compat','sts-enabled':False},'storage-credential':{'type':'s3','credential-type':'access-key','access-key-id':'labadmin','secret-access-key':'lab_local_password'}}))
    print('Warehouse ready')
