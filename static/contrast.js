(function(){
  function getEffectiveBackground(el){
    let node = el;
    while(node && node !== document){
      const style = getComputedStyle(node);
      const bgImg = style.backgroundImage;
      const bg = style.backgroundColor;
      if(bgImg && bgImg !== 'none' && bgImg !== 'initial'){
        return {type: 'gradient'};
      }
      if(bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent'){
        return {type: 'color', value: bg};
      }
      node = node.parentElement;
    }
    return {type: 'color', value: getComputedStyle(document.body).backgroundColor};
  }

  function parseRgbString(rgb){
    // handles rgb(), rgba(), and hex fallback
    if(!rgb) return null;
    rgb = rgb.trim();
    if(rgb[0] === '#'){
      let r = parseInt(rgb.substr(1,2),16);
      let g = parseInt(rgb.substr(3,2),16);
      let b = parseInt(rgb.substr(5,2),16);
      return [r,g,b];
    }
    const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if(m){
      return [parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10)];
    }
    return null;
  }

  function luminance(rgb){
    // rgb array [r,g,b] 0-255
    const r = rgb[0]/255; const g = rgb[1]/255; const b = rgb[2]/255;
    // standard relative luminance
    const R = (r <= 0.03928) ? (r/12.92) : Math.pow((r+0.055)/1.055,2.4);
    const G = (g <= 0.03928) ? (g/12.92) : Math.pow((g+0.055)/1.055,2.4);
    const B = (b <= 0.03928) ? (b/12.92) : Math.pow((b+0.055)/1.055,2.4);
    return 0.2126*R + 0.7152*G + 0.0722*B;
  }

  function pickTextColor(bg){
    if(!bg) return '#ffffff';
    if(bg.type === 'gradient') return '#ffffff';
    const rgb = parseRgbString(bg.value);
    if(!rgb) return '#ffffff';
    const lum = luminance(rgb);
    // WCAG: choose threshold roughly 0.5
    return (lum > 0.5) ? '#050505' : '#ffffff';
  }

  function adjustContrast(){
    const selectors = [
      '.brand-badge',
      '.example-btn .stButton > button',
      '.stButton > button',
      '.info-banner',
      '.result-box',
      '.quick-summary',
      '.watchlist-title'
    ];
    selectors.forEach(sel=>{
      document.querySelectorAll(sel).forEach(el=>{
        try{
          const bg = getEffectiveBackground(el);
          const text = pickTextColor(bg);
          el.style.setProperty('color', text, 'important');
          // if element is a button, ensure inner text uses same
          if(el.tagName === 'DIV'){
            const btn = el.querySelector('button');
            if(btn) btn.style.setProperty('color', text, 'important');
          }
        }catch(e){
          // ignore
        }
      })
    })
  }

  document.addEventListener('DOMContentLoaded', function(){
    adjustContrast();
    // also run after slight delay and periodically to catch dynamic updates
    setTimeout(adjustContrast, 500);
    setInterval(adjustContrast, 1500);
  });
})();
