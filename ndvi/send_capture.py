#!/usr/bin/env python3
import argparse,json,mimetypes,os,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--pi',default='http://127.0.0.1:8765')
 p.add_argument('--red',type=Path,required=True);p.add_argument('--nir',type=Path,required=True)
 p.add_argument('--flight-id',default='voo_teste');p.add_argument('--capture-id',default=None)
 p.add_argument('--api-key',default=os.getenv('AGRODT_API_KEY'))
 a=p.parse_args()
 if not a.api_key:p.error('Defina AGRODT_API_KEY')
 boundary='agrodt-'+uuid.uuid4().hex
 body=bytearray()
 for k,v in [('capture_id',a.capture_id or uuid.uuid4().hex[:12]),('flight_id',a.flight_id)]:
  body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
 for k,path in [('red',a.red),('nir',a.nir)]:
  body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{path.name}"\r\nContent-Type: {mimetypes.guess_type(path.name)[0] or "application/octet-stream"}\r\n\r\n').encode()
  body+=path.read_bytes()+b'\r\n'
 body+=(f'--{boundary}--\r\n').encode()
 request=Request(a.pi.rstrip('/')+'/api/v1/captures',data=bytes(body),method='POST',headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-API-Key':a.api_key})
 try:
  with urlopen(request,timeout=180) as resp: code,res=resp.status,json.load(resp)
 except HTTPError as e:code,res=e.code,json.load(e)
 print(json.dumps({'http_status':code,'result':res},indent=2,ensure_ascii=False))
 if code!=201:raise SystemExit(1)
if __name__=='__main__':main()
