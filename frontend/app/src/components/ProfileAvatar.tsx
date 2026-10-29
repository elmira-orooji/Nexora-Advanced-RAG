import {useEffect, useRef, useState} from "react";
import {useTranslation} from "react-i18next";
import {API_URL} from "../config/api";
import "../styles/profile-avatar.css";
export function AccountAvatar({initials}: {initials:string}) {
 const [version,setVersion]=useState(Date.now()); const [failed,setFailed]=useState(false);
 useEffect(()=>{const refresh=()=>{setFailed(false);setVersion(Date.now());};window.addEventListener("avatar-updated",refresh);return()=>window.removeEventListener("avatar-updated",refresh);},[]);
 return failed ? <>{initials}</> : <img className="account-avatar-image" src={`${API_URL}/auth/avatar?v=${version}`} alt="" onError={()=>setFailed(true)}/>;
}
export default function ProfileAvatar(){
 const {i18n}=useTranslation();const fa=i18n.language.startsWith("fa");const input=useRef<HTMLInputElement>(null);
 const [busy,setBusy]=useState(false);const [message,setMessage]=useState("");const [error,setError]=useState("");
 async function save(value:File|string|null){if(busy)return;setBusy(true);setError("");setMessage("");try{
 let file:Blob|null=value instanceof File?value:null;
 if(typeof value==="string"){const source=await fetch(value);if(!source.ok)throw new Error();file=await source.blob();}
 if(file&&(!["image/png","image/jpeg","image/webp"].includes(file.type)||file.size>5*1024*1024))throw new Error();
 const result=await fetch(`${API_URL}/auth/avatar`,{method:file?"PUT":"DELETE",credentials:"include",headers:file?{"Content-Type":file.type}:{},body:file});
 if(!result.ok)throw new Error();window.dispatchEvent(new Event("avatar-updated"));setMessage(fa?"عکس کاربری ذخیره شد.":"Profile photo updated.");
 }catch{setError(fa?"ذخیرهٔ عکس انجام نشد. تصویر PNG، JPG یا WebP تا ۵ مگابایت انتخاب کنید.":"Could not save photo. Choose a PNG, JPG or WebP up to 5 MB.");}finally{setBusy(false);if(input.current)input.current.value="";}}
 return <section className="preferences-card"><div className="preferences-section-heading"><div><h2>{fa?"عکس کاربری":"Profile photo"}</h2><p>{fa?"از آواتارهای پیشنهادی انتخاب کنید یا عکس خود را بارگذاری کنید.":"Choose a suggested avatar or upload your own photo."}</p></div></div><div className="profile-avatar-actions"><span className="profile-avatar-preview"><AccountAvatar initials="U"/></span><button type="button" disabled={busy} className="preferences-password-submit" onClick={()=>input.current?.click()}>{fa?"انتخاب از دستگاه":"Upload photo"}</button><button type="button" disabled={busy} onClick={()=>void save(null)}>{fa?"حذف عکس":"Remove photo"}</button></div><div className="profile-avatar-grid" role="group" aria-label={fa?"آواتارهای پیشنهادی":"Suggested avatars"}>{Array.from({length:10},(_,i)=>{const url=`/avatars/avatar-${String(i+1).padStart(2,"0")}.png`;return <button type="button" key={url} disabled={busy} aria-label={(fa?"انتخاب آواتار ":"Choose avatar ")+(i+1)} onClick={()=>void save(url)}><img src={url} alt=""/></button>;})}</div><input hidden type="file" ref={input} accept="image/png,image/jpeg,image/webp" onChange={e=>{const file=e.target.files?.[0];if(file)void save(file);}}/>{message&&<p role="status">{message}</p>}{error&&<p role="alert" className="preferences-password-error">{error}</p>}</section>;
}
