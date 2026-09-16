var I18N=JSON.parse(document.getElementById('i18n-strings').textContent);function parseCSV(text){const rows=[];let row=[],cell='',q=false;for(let i=0;i<text.length;i++){const c=text[i],n=text[i+1];if(c==='"'&&q&&n==='"'){cell+='"';i++;continue}if(c==='"'){q=!q;continue}if(c===','&&!q){row.push(cell);cell='';continue}if((c==='\n'||c==='\r')&&!q){if(c==='\r'&&n==='\n')i++;row.push(cell);if(row.some(v=>v!==''))rows.push(row);row=[];cell='';continue}cell+=c}if(cell||row.length){row.push(cell);rows.push(row)}const header=rows.shift()||[];return rows.map(r=>Object.fromEntries(header.map((h,i)=>[h,r[i]||''])))}function agencyCards(){const el=document.querySelector('.agency-grid');if(!el)return;const data=JSON.parse(el.dataset.agencies);const labels={CPSC:I18N.agency_CPSC,FDA:I18N.agency_FDA,FSIS:I18N.agency_FSIS,NHTSA:I18N.agency_NHTSA,USCG:I18N.agency_USCG};el.innerHTML=Object.entries(data).map(([k,v])=>`<article class="agency-card"><span>${k}</span><strong>${v.toLocaleString()}</strong><small>${labels[k]}</small><a href="agencies/${k.toLowerCase()}.html">${I18N.agency_link}</a></article>`).join('')}function hazardBars(){const el=document.querySelector('.hazard-bars');if(!el)return;const data=JSON.parse(el.dataset.hazards);const entries=Object.entries(data).sort((a,b)=>b[1]-a[1]).slice(0,8);const max=entries[0]?.[1]||1;el.innerHTML=entries.map(([k,v])=>`<div class="hazard-bar"><strong>${k}</strong><div class="track"><div class="fill" style="width:${Math.max(3,v/max*100)}%"></div></div><span>${v.toLocaleString()}</span></div>`).join('')}async function preview(){const body=document.querySelector('#recall-preview tbody');if(!body)return;try{const res=await fetch('/samples/recalls.csv');const rows=parseCSV(await res.text()).slice(0,8);body.innerHTML=rows.map(r=>`<tr><td>${r.source_agency}</td><td>${r.recall_date}</td><td>${r.title}</td><td>${r.hazard_keys}</td></tr>`).join('')}catch(e){body.innerHTML='<tr><td colspan="4"></td></tr>';body.querySelector('td').textContent=I18N.preview_error}}agencyCards();hazardBars();preview();
var contactForm = document.getElementById("contactForm");
var contactSuccess = document.getElementById("contactSuccess");
var contactError = null;

function ensureContactError() {
  if (contactError || !contactForm) return contactError;
  contactError = document.createElement("p");
  contactError.className = "form-error";
  contactError.setAttribute("role", "alert");
  contactError.style.display = "none";
  contactForm.appendChild(contactError);
  return contactError;
}

function showContactSuccess() {
  if (contactForm) {
    contactForm.reset();
    contactForm.style.display = "none";
  }
  if (contactError) contactError.style.display = "none";
  if (contactSuccess) {
    contactSuccess.style.display = "block";
    contactSuccess.focus({ preventScroll: true });
    contactSuccess.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

if (new URLSearchParams(window.location.search).get("submitted") === "1") {
  showContactSuccess();
}

if (contactForm) {
  contactForm.addEventListener("submit", async function (event) {
    if (!window.fetch || !window.FormData) return;
    event.preventDefault();

    var submitButton = contactForm.querySelector("button[type=submit]");
    var submitLabel = submitButton ? submitButton.querySelector("span") : null;
    var originalLabel = submitLabel ? submitLabel.textContent : I18N.submit_label;
    var errorBox = ensureContactError();
    var sent = false;

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.classList.add("is-submitting");
      submitButton.setAttribute("aria-busy", "true");
    }
    if (submitLabel) submitLabel.textContent = I18N.sending;
    if (errorBox) errorBox.style.display = "none";

    try {
      var response = await fetch(contactForm.action, {
        method: "POST",
        body: new FormData(contactForm),
        headers: { Accept: "application/json" },
      });
      var payload = {};
      try {
        payload = await response.json();
      } catch (_) {}
      if (!response.ok || payload.success === false) {
        throw new Error(payload.message || "The request could not be sent.");
      }
      sent = true;
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", window.location.pathname + "?submitted=1#contact");
      }
      showContactSuccess();
    } catch (_) {
      if (errorBox) {
        errorBox.textContent = I18N.send_error;
        errorBox.style.display = "block";
      }
    } finally {
      if (!sent && submitButton) {
        submitButton.disabled = false;
        submitButton.classList.remove("is-submitting");
        submitButton.removeAttribute("aria-busy");
      }
      if (!sent && submitLabel) submitLabel.textContent = originalLabel;
    }
  });
}

function resetContactForm() {
  if (contactForm) {
    contactForm.reset();
    contactForm.style.display = "grid";
  }
  if (contactSuccess) contactSuccess.style.display = "none";
  if (contactError) contactError.style.display = "none";
  if (window.history && window.history.replaceState) {
    window.history.replaceState(null, "", window.location.pathname + "#contact");
  }
}