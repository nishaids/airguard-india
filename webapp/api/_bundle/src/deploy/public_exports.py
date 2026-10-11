"""Strip machine-local paths at the public export boundary, leaving metrics intact."""
from pathlib import Path
import re
import json
from src import config

LOCAL_PATH = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/')


def sanitize_text(text):
    pattern = r'(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|/Users/)[^\r\n`"<>]*'
    return re.sub(pattern,'[local path omitted from public export]',text)


def sanitize(value):
    if isinstance(value, dict): return {k:sanitize(v) for k,v in value.items()}
    if isinstance(value, list): return [sanitize(v) for v in value]
    if isinstance(value,str) and LOCAL_PATH.search(value):
        root=str(config.PROJECT_ROOT)
        if value.startswith(root+'\\') or value.startswith(root+'/'):
            return value[len(root)+1:].replace('\\','/')
        return '[local path omitted from public export]'
    return value


def sanitize_directory(directory):
    changed=[]
    for path in sorted(Path(directory).rglob('*.json')):
        value=json.loads(path.read_text(encoding='utf-8'))
        safe=sanitize(value)
        if safe!=value:
            path.write_text(json.dumps(safe,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
            changed.append(path.name)
    for path in sorted(Path(directory).glob('*.md')):
        original=path.read_text(encoding='utf-8');safe=sanitize_text(original)
        if original!=safe:
            path.write_text(safe,encoding='utf-8');changed.append(path.name)
    return changed


if __name__=='__main__':
    changed=sanitize_directory(config.PROJECT_ROOT/'webapp/public/data')
    print(json.dumps({'sanitized_public_json_files':changed,'numeric_results_modified':False}))
