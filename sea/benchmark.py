"""Offline paired video-QA evaluation; no model calls, downloads or invented results."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

MAX_JSON=8*1024*1024
MAX_VIDEO=2*1024**3
MAX_CLIPS=200
MAX_QUESTIONS=2000
SCHEMA=1
CONDITIONS=('baseline','sea')


def unique_object(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError('Duplicate JSON key: '+k)
        result[k]=v
    return result


def load(path):
    with Path(path).open('rb') as f:
        raw=f.read(MAX_JSON+1)
    if len(raw)>MAX_JSON:
        raise ValueError('JSON exceeds 8 MiB.')
    def invalid(value):
        raise ValueError('Nonfinite JSON: '+value)
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_object,parse_constant=invalid)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                     ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):
        raise ValueError('IDs must contain 1–80 ASCII letters, digits, underscores or hyphens.')
    return value


def text(value,maximum=2000):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum:
        raise ValueError('Invalid or oversized text field.')
    return value


def exact(obj,keys):
    if not isinstance(obj,dict) or set(obj)!=set(keys.split()):
        raise ValueError('Expected fields: '+keys)


def media_file(root,name):
    root=Path(root).resolve(strict=True)
    rel=Path(text(name,500))
    if not root.is_dir() or rel.is_absolute() or '..' in rel.parts or rel.suffix.lower()!='.mp4':
        raise ValueError('Use relative MP4 paths within the benchmark media directory.')
    path=(root/rel).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or not 0<path.stat().st_size<=MAX_VIDEO:
        raise ValueError('Expected a nonempty local MP4 within the media root, at most 2 GiB.')
    return path


def file_hash(path):
    before=path.stat()
    h=hashlib.sha256()
    with path.open('rb') as f:
        total=0
        for block in iter(lambda:f.read(1024*1024),b''):
            total+=len(block)
            if total>MAX_VIDEO:
                raise ValueError('Media exceeds size limit.')
            h.update(block)
    after=path.stat()
    if total!=before.st_size or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('Video changed while hashing.')
    return h.hexdigest()


def validate_suite(suite):
    exact(suite,'schema_version name clips')
    if type(suite['schema_version']) is not int or suite['schema_version']!=SCHEMA:
        raise ValueError('Unsupported benchmark schema.')
    text(suite['name'],200)
    clips=suite['clips']
    if not isinstance(clips,list) or not 1<=len(clips)<=MAX_CLIPS:
        raise ValueError('Expected 1–200 clips.')
    clip_ids=set()
    hashes=set()
    questions={}
    for clip in clips:
        exact(clip,'id file sha256 source_kind source questions')
        cid=ident(clip['id'])
        sha=clip['sha256']
        if cid in clip_ids or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or sha in hashes:
            raise ValueError('Duplicate clip ID/content or invalid SHA-256.')
        clip_ids.add(cid)
        hashes.add(sha)
        text(clip['file'],500)
        text(clip['source'])
        if clip['source_kind'] not in ('real','synthetic'):
            raise ValueError('Choose real or synthetic source_kind.')
        if not isinstance(clip['questions'],list) or not clip['questions']:
            raise ValueError('Every clip needs questions.')
        for q in clip['questions']:
            exact(q,'id category question options')
            qid=ident(q['id'])
            if qid in questions or len(questions)>=MAX_QUESTIONS:
                raise ValueError('Duplicate question ID or too many questions.')
            ident(q['category'])
            text(q['question'])
            opts=q['options']
            if not isinstance(opts,list) or not 2<=len(opts)<=6:
                raise ValueError('Use 2–6 multiple-choice options.')
            if len({text(x,1000).strip().casefold() for x in opts})!=len(opts):
                raise ValueError('Options must be distinct.')
            questions[qid]=(clip,q)
    return questions


def answer(value,q,allow_null):
    if value is None and allow_null:
        return value
    if type(value) is not int or not 0<=value<len(q['options']):
        raise ValueError('Answer must be a zero-based option index'+(' or null.' if allow_null else '.'))
    return value


def prepare(spec,root):
    exact(spec,'name clips')
    if not isinstance(spec['clips'],list) or not 1<=len(spec['clips'])<=MAX_CLIPS:
        raise ValueError('Expected 1–200 clips.')
    suite={'schema_version':SCHEMA,'name':spec['name'],'clips':[]}
    key={}
    for clip in spec['clips']:
        exact(clip,'id file source_kind source questions')
        if not isinstance(clip['questions'],list) or not clip['questions']:
            raise ValueError('Every clip needs questions.')
        row={k:v for k,v in clip.items() if k!='questions'}
        row['sha256']=file_hash(media_file(root,clip['file']))
        row['questions']=[]
        for q in clip['questions']:
            exact(q,'id category question options answer')
            qid=ident(q['id'])
            if qid in key or len(key)>=MAX_QUESTIONS:
                raise ValueError('Duplicate question ID or too many questions.')
            key[qid]=q['answer']
            row['questions'].append({k:v for k,v in q.items() if k!='answer'})
        suite['clips'].append(row)
    qs=validate_suite(suite)
    for qid,(_,q) in qs.items():
        answer(key[qid],q,False)
    return suite,{'suite_id':digest(suite),'answers':key}


def packet(suite,clip_id,root):
    validate_suite(suite)
    clip=next((c for c in suite['clips'] if c['id']==clip_id),None)
    if clip is None:
        raise ValueError('Unknown clip.')
    path=media_file(root,clip['file'])
    if file_hash(path)!=clip['sha256']:
        raise ValueError('Video content changed; use the original frozen media.')
    # No source description, category, answers or other clips in the model packet.
    return {'suite_id':digest(suite),'clip_id':clip_id,'media_path':str(path),'media_sha256':clip['sha256'],
            'instructions':'Use the supplied video evidence. Answer every question with its zero-based option index, or null if evidence is insufficient. Return a JSON object mapping question IDs to answers. Do not consult answer keys, external sources or other runs.',
            'questions':[{k:q[k] for k in ('id','question','options')} for q in clip['questions']]}


def validate_protocol(p):
    exact(p,'pair_id model host settings shared_input budget')
    for k in ('pair_id','model','host','settings','shared_input','budget'):
        text(p[k],2000)


def template(suite,condition,protocol):
    qs=validate_suite(suite)
    validate_protocol(protocol)
    if condition not in CONDITIONS:
        raise ValueError('Unknown condition.')
    return {'suite_id':digest(suite),'condition':condition,'protocol':protocol,
            'answers':{qid:None for qid in qs},
            'clip_runs':{c['id']:{'status':'pending','tool_calls':0,'elapsed_s':None}
                         for c in suite['clips']}}


def validate_run(run,condition,suite,qs):
    exact(run,'suite_id condition protocol answers clip_runs')
    if run['suite_id']!=digest(suite) or run['condition']!=condition:
        raise ValueError('Run suite or condition mismatch.')
    validate_protocol(run['protocol'])
    answers=run['answers']
    if not isinstance(answers,dict) or set(answers)!=set(qs):
        raise ValueError('Every question must have one explicit answer or null.')
    for qid,(_,q) in qs.items():
        answer(answers[qid],q,True)
    logs=run['clip_runs']
    if not isinstance(logs,dict) or set(logs)!={c['id'] for c in suite['clips']}:
        raise ValueError('Every clip must have a run record.')
    for clip in suite['clips']:
        log=logs[clip['id']]
        exact(log,'status tool_calls elapsed_s')
        if log['status'] not in ('completed','error'):
            raise ValueError('Finalize every clip: completed or error.')
        n,t=log['tool_calls'],log['elapsed_s']
        if type(n) is not int or not 0<=n<=100000 or (condition=='baseline' and n!=0):
            raise ValueError('Invalid SEA tool count; baseline must have zero calls.')
        if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=86400:
            raise ValueError('Record elapsed seconds for every clip.')
        if log['status']=='error' and any(answers[q['id']] is not None for q in clip['questions']):
            raise ValueError('Failed clips require null answers.')


def summarize(items):
    n=len(items)
    b=sum(x['baseline_correct'] for x in items)
    s=sum(x['sea_correct'] for x in items)
    win=sum(not x['baseline_correct'] and x['sea_correct'] for x in items)
    loss=sum(x['baseline_correct'] and not x['sea_correct'] for x in items)
    return {'questions':n,'baseline_correct':b,'sea_correct':s,
            'baseline_accuracy':round(b/n,6),'sea_accuracy':round(s/n,6),
            'delta_percentage_points':round(100*(s-b)/n,4),
            'improved':win,'regressed':loss,'both_correct':b-loss,'both_incorrect':n-b-win,
            'baseline_abstentions':sum(x['baseline_answer'] is None for x in items),
            'sea_abstentions':sum(x['sea_answer'] is None for x in items)}


def score(suite,key,baseline,assisted):
    qs=validate_suite(suite)
    exact(key,'suite_id answers')
    if key['suite_id']!=digest(suite) or not isinstance(key['answers'],dict) or set(key['answers'])!=set(qs):
        raise ValueError('Answer key does not match suite.')
    for qid,(_,q) in qs.items():
        answer(key['answers'][qid],q,False)
    validate_run(baseline,'baseline',suite,qs)
    validate_run(assisted,'sea',suite,qs)
    if baseline['protocol']!=assisted['protocol']:
        raise ValueError('Paired runs must use the same model, host, settings, input, budget and pair ID.')
    rows=[]
    for qid,(clip,q) in qs.items():
        b,s,k=baseline['answers'][qid],assisted['answers'][qid],key['answers'][qid]
        rows.append({'id':qid,'clip_id':clip['id'],'source_kind':clip['source_kind'],'category':q['category'],
                     'baseline_answer':b,'sea_answer':s,'correct_answer':k,
                     'baseline_correct':b==k,'sea_correct':s==k})
    groups={}
    for field in ('category','source_kind','clip_id'):
        groups[field]={v:summarize([r for r in rows if r[field]==v]) for v in sorted({r[field] for r in rows})}
    perclip=list(groups['clip_id'].values())
    macro_b=sum(r['baseline_correct']/r['questions'] for r in perclip)/len(perclip)
    macro_s=sum(r['sea_correct']/r['questions'] for r in perclip)/len(perclip)
    return {'suite_id':digest(suite),'protocol':baseline['protocol'],'clips':len(perclip),
            'overall':summarize(rows),'by_category':groups['category'],'by_source_kind':groups['source_kind'],
            'by_clip':groups['clip_id'],'clip_macro_accuracy':{'baseline':round(macro_b,6),'sea':round(macro_s,6),
                          'delta_percentage_points':round(100*(macro_s-macro_b),4)},
            'run_summary':{cond:{'elapsed_s':round(sum(x['elapsed_s'] for x in run['clip_runs'].values()),3),
                                 'failed_clips':sum(x['status']=='error' for x in run['clip_runs'].values()),
                                 'sea_tool_calls':sum(x['tool_calls'] for x in run['clip_runs'].values())}
                           for cond,run in (('baseline',baseline),('sea',assisted))},
            'assisted_clips_without_sea_calls':[cid for cid,log in assisted['clip_runs'].items() if log['tool_calls']==0],
            'questions':rows,
            'limitations':['Descriptive paired accuracy; not a significance test or proof of general video understanding.',
                           'Abstentions and failed clips count as incorrect; real and synthetic sources are reported separately.',
                           'Run metadata and tool counts are operator-reported, not independently attested.',
                           'The answer key must remain hidden, and actual media exposure and budgets must be controlled by the operator.']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    prep.add_argument('spec');prep.add_argument('media_root');prep.add_argument('output_dir',type=Path)
    pack=sub.add_parser('packet')
    pack.add_argument('suite');pack.add_argument('clip_id');pack.add_argument('media_root')
    run=sub.add_parser('run-template')
    run.add_argument('suite');run.add_argument('condition',choices=CONDITIONS);run.add_argument('protocol')
    evaluate=sub.add_parser('score')
    for name in ('suite','key','baseline','assisted'):
        evaluate.add_argument(name)
    a=p.parse_args(argv)
    try:
        if a.action=='prepare':
            suite,key=prepare(load(a.spec),a.media_root)
            a.output_dir.mkdir()
            for name,data in (('suite.json',suite),('key.json',key)):
                with (a.output_dir/name).open('x',encoding='utf-8') as f:
                    json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False)
            result={'suite_id':digest(suite),'clips':len(suite['clips']),'output':str(a.output_dir),
                    'warning':'Keep key.json and the original spec outside the model-accessible directory.'}
        elif a.action=='packet':
            result=packet(load(a.suite),a.clip_id,a.media_root)
        elif a.action=='run-template':
            result=template(load(a.suite),a.condition,load(a.protocol))
        else:
            result=score(load(a.suite),load(a.key),load(a.baseline),load(a.assisted))
        print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
        return 0
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(f'SEA benchmark: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
