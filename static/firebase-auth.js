import { initializeApp } from "https://www.gstatic.com/firebasejs/12.1.0/firebase-app.js";
import {
  getAuth, RecaptchaVerifier, signInWithPhoneNumber,
  signInWithEmailAndPassword, createUserWithEmailAndPassword,
  GoogleAuthProvider, signInWithPopup, onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/12.1.0/firebase-auth.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

const $ = (id) => document.getElementById(id);
const setStatus = (id, text) => { $(id).textContent = text; };

// Switch login methods
document.querySelectorAll(".auth-tabs button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".auth-tabs button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".auth-method").forEach(m => m.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.method).classList.add("active");
  });
});

// Redirect already signed-in users
onAuthStateChanged(auth, user => {
  if (user) window.location.href = "/";
});

// Phone OTP
let confirmationResult = null;
let recaptcha = null;

function setupRecaptcha() {
  if (recaptcha) return;
  recaptcha = new RecaptchaVerifier(auth, "recaptcha-container", {
    size: "normal",
    callback: () => setStatus("phone-status", "✓ Verification ready. OTP भेज सकते हैं।"),
    "expired-callback": () => setStatus("phone-status", "reCAPTCHA expire हो गया। फिर कोशिश करें।")
  });
  recaptcha.render().catch(err => setStatus("phone-status", err.message));
}

setupRecaptcha();

$("send-otp").addEventListener("click", async () => {
  const phone = $("phone-number").value.trim();
  if (!/^\+\d{8,15}$/.test(phone)) {
    setStatus("phone-status", "कृपया +91XXXXXXXXXX जैसे सही नंबर डालें।");
    return;
  }
  try {
    setStatus("phone-status", "OTP भेजा जा रहा है...");
    confirmationResult = await signInWithPhoneNumber(auth, phone, recaptcha);
    $("otp-area").style.display = "block";
    setStatus("phone-status", "✓ OTP आपके मोबाइल पर भेज दिया गया है।");
  } catch (e) {
    setStatus("phone-status", "OTP नहीं भेजा जा सका: " + friendlyError(e));
  }
});

$("verify-otp").addEventListener("click", async () => {
  if (!confirmationResult) return;
  const code = $("otp-code").value.trim();
  if (!/^\d{6}$/.test(code)) {
    setStatus("phone-status", "6 अंकों का OTP डालें।");
    return;
  }
  try {
    await confirmationResult.confirm(code);
    window.location.href = "/";
  } catch (e) {
    setStatus("phone-status", "OTP गलत या expired है।");
  }
});

// Email + password
$("email-login").addEventListener("click", async () => {
  try {
    await signInWithEmailAndPassword(auth, $("email-address").value.trim(), $("email-password").value);
    window.location.href = "/";
  } catch (e) {
    setStatus("email-status", "Login नहीं हुआ: " + friendlyError(e));
  }
});

$("email-signup").addEventListener("click", async () => {
  try {
    await createUserWithEmailAndPassword(auth, $("email-address").value.trim(), $("email-password").value);
    window.location.href = "/";
  } catch (e) {
    setStatus("email-status", "Account नहीं बना: " + friendlyError(e));
  }
});

// Google
$("google-login").addEventListener("click", async () => {
  try {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
    window.location.href = "/";
  } catch (e) {
    setStatus("google-status", "Google Login नहीं हुआ: " + friendlyError(e));
  }
});

function friendlyError(e) {
  const code = e?.code || "";
  const map = {
    "auth/invalid-email": "Email सही नहीं है।",
    "auth/invalid-credential": "Email या password सही नहीं है।",
    "auth/email-already-in-use": "यह Email पहले से registered है।",
    "auth/weak-password": "Password कम से कम 6 अक्षरों का रखें।",
    "auth/popup-closed-by-user": "Google Login window बंद कर दी गई।",
    "auth/too-many-requests": "बहुत कोशिशें हो गई हैं। थोड़ी देर बाद फिर करें।",
    "auth/quota-exceeded": "OTP limit पूरी हो गई है। थोड़ी देर बाद फिर करें।"
  };
  return map[code] || e?.message || "कृपया फिर कोशिश करें।";
}
