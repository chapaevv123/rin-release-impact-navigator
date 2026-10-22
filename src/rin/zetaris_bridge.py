"""Local Zetaris SQL adapter through its existing Compose network.

Windows Docker port forwarding currently resets HTTP; credentials stay on stdin
to a transient Node process inside the existing UI container. This helper never
prints the bearer, password, or raw authentication response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone

JS = r"""
let data='';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', async () => {
  try {
    const input = JSON.parse(data);
    const loginResponse = await fetch('http://127.0.0.1:3000/api/auth/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({username:input.username,password:input.password})
    });
    const login = await loginResponse.json();
    const token = login.idToken || login.token || login.accessToken;
    const orgId = Number(login.orgId);
    if (loginResponse.status !== 200 || !token || !Number.isInteger(orgId)) {
      console.log(JSON.stringify({result:'AUTH_BLOCKED',login_http_status:loginResponse.status,
        token_present:!!token,org_id_present:Number.isInteger(orgId)})); return;
    }
    const response = await fetch('http://api:8888/api/v1.0/sql-editor/sqls/run', {
      method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json',
        'Authorization':'Bearer '+token,'X-Org-ID':String(orgId),'X-Request-ID':input.request_id},
      body:JSON.stringify({queryId:input.request_id,sql:input.sql,source:'SqlEditor',limit:10})
    });
    const raw = await response.text();
    let parsed; try { parsed=JSON.parse(raw); } catch { parsed=null; }
    const rows = parsed && (parsed.data || parsed.rows || parsed.result);
    console.log(JSON.stringify({result:'SQL_PROBE',http_status:response.status,
      query_id:input.request_id,sql:input.sql,response_bytes:raw.length,
      top_keys:parsed && typeof parsed==='object' ? Object.keys(parsed).slice(0,20):[],
      headers:parsed && Array.isArray(parsed.headers) ? parsed.headers.slice(0,20):null,
      rows:Array.isArray(rows)?rows.slice(0,10):null,
      server_message: response.status>=400 && parsed && typeof parsed.msg==='string'
        ? parsed.msg.slice(0,500):null,
      error_http_status:response.status>=400?response.status:null}));
  } catch (error) { console.log(JSON.stringify({result:'BRIDGE_ERROR',error_type:error.name})); }
});
"""


def env_value(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing Zetaris environment field: {name}")
    return value


def run(sql: str) -> dict:
    if not sql.strip().lower().startswith("select ") or ";" in sql or " limit 10" not in sql.lower():
        raise ValueError("only one SELECT bounded by LIMIT 10 is permitted")
    request_id = str(uuid.uuid4())
    payload = {"username": env_value("ZETARIS_ADMIN_EMAIL"),
               "password": env_value("ZETARIS_ADMIN_PASSWORD"),
               "sql": sql, "request_id": request_id}
    completed = subprocess.run(["docker", "exec", "-i", "zetaris-ui-1", "node", "-e", JS],
                               input=json.dumps(payload), text=True, capture_output=True, timeout=70)
    if completed.returncode:
        return {"result": "BRIDGE_FAILED", "exit_code": completed.returncode}
    try:
        result = json.loads(completed.stdout)
        result["at_utc"] = datetime.now(timezone.utc).isoformat()
        result["result_sha256"] = hashlib.sha256(json.dumps(result.get("rows"), sort_keys=True).encode()).hexdigest()
        return result
    except ValueError:
        return {"result": "INVALID_BRIDGE_RESPONSE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", default="SELECT 1 AS one")
    args = parser.parse_args()
    print(json.dumps(run(args.sql)))
