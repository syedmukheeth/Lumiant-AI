// Applies a saved theme before first paint (no flash). Loaded as a same-origin script so the CSP needs no inline script.
try{var t=localStorage.getItem("lumiant-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch{}
