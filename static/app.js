/* Downloader behaviour shared by every page that contains the tool. */
(function(){
 if(!document.getElementById('f'))return;
 const PUBLIC_MODE=document.body.dataset.public==='true';
 const $=id=>document.getElementById(id);
 const setMsg=(text,error=false)=>{$('msg').textContent=text;$('msg').className=error?'err':''};
 let current=null, generation=0, controller=null, downloading=false, fetchingURL=null;
 async function readJSON(res){
  const type=res.headers.get('Content-Type')||'';
  if(!type.includes('application/json'))throw new Error('The server could not complete this request. Please try again.');
  return res.json();
 }
 async function download(asset,button){
  if(!current || downloading)return;
  downloading=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);setMsg(asset==='all'?'Preparing your ZIP…':'Downloading attachment…');
  try{
   const res=await fetch('/api/download?'+new URLSearchParams({session:current.session,asset}));
   if(!res.ok){const data=await readJSON(res);throw new Error(data.error||'Download failed.')}
   const blob=await res.blob(), link=document.createElement('a'), objectURL=URL.createObjectURL(blob);
   const disposition=res.headers.get('Content-Disposition')||'';
   const encoded=disposition.match(/filename\*=UTF-8''([^;]+)/i), plain=disposition.match(/filename="?([^";]+)"?/i);
   link.download=encoded?decodeURIComponent(encoded[1]):plain?plain[1]:'download';
   link.href=objectURL;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(objectURL),60000);
   setMsg('Download ready. Check your browser downloads.');
  }catch(err){setMsg(err.message,true)}finally{document.querySelectorAll('button').forEach(b=>b.disabled=false);downloading=false}
 }
 $('url').addEventListener('paste',()=>setTimeout(()=>{if(PUBLIC_MODE&&!$('ack').checked){setMsg('Tick the confirmation box, then press Fetch media.',true);return}$('f').requestSubmit()},0));
 $('f').addEventListener('submit',async e=>{
  e.preventDefault();if(downloading){setMsg('Wait for the current download to finish.');return}
  if(PUBLIC_MODE&&!$('ack').checked){setMsg('Please confirm that you own this content or have permission to download it.',true);return}
  const enteredURL=$('url').value.trim();if(fetchingURL===enteredURL)return;fetchingURL=enteredURL;
  controller?.abort();controller=new AbortController();const mine=++generation;
  current=null;$('result').hidden=true;$('go').disabled=true;$('f').classList.add('busy');setMsg('Finding available media…');
  try{
   const res=await fetch('/api/info',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:enteredURL,ack:PUBLIC_MODE?$('ack').checked:undefined}),signal:controller.signal});
   const data=await readJSON(res);if(mine!==generation)return;if(!res.ok)throw new Error(data.error||'Could not fetch this post.');
   current=data;$('who').textContent=({linkedin:'LinkedIn',pinterest:'Pinterest'}[data.platform]||'Instagram')+(data.uploader?' · '+data.uploader:'');$('caption').textContent=data.title;
   $('warnings').textContent=(data.warnings||[]).join(' ');$('assets').replaceChildren();
   for(const asset of data.assets){
    const card=document.createElement('article');card.className='asset';
    if(asset.thumbnail){const img=document.createElement('img');img.className='preview';img.src=asset.thumbnail;img.alt=asset.label;img.referrerPolicy='no-referrer';img.loading='lazy';img.addEventListener('error',()=>{const placeholder=document.createElement('div');placeholder.className='placeholder';placeholder.textContent=asset.kind==='video'?'▶':'▤';img.replaceWith(placeholder)},{once:true});card.append(img)}
    else{const placeholder=document.createElement('div');placeholder.className='placeholder';placeholder.textContent=asset.kind==='video'?'▶':'▤';card.append(placeholder)}
    const meta=document.createElement('div');meta.className='asset-meta';const label=document.createElement('p');label.textContent=asset.label;
    const button=document.createElement('button');button.className='btn sm';button.textContent=asset.kind==='video'?'Download video':asset.kind==='document'?'Download PDF':'Download image';button.addEventListener('click',()=>download(asset.id,button));meta.append(label,button);card.append(meta);$('assets').append(card);
   }
   $('all').hidden=data.assets.length<2;$('result').hidden=false;$('result').scrollIntoView({behavior:'smooth',block:'start'});setMsg(`${data.assets.length} attachment${data.assets.length===1?'':'s'} ready · links expire in 15 minutes`);
  }catch(err){if(mine===generation&&err.name!=='AbortError')setMsg(err.message,true)}finally{if(mine===generation){$('go').disabled=false;$('f').classList.remove('busy');fetchingURL=null}}
 });
 $('all').addEventListener('click',()=>download('all',$('all')));
 $('again').addEventListener('click',()=>{if(downloading)return;controller?.abort();generation++;current=null;fetchingURL=null;$('result').hidden=true;$('go').disabled=false;$('f').classList.remove('busy');$('url').value='';setMsg('');$('url').focus()});
})();
