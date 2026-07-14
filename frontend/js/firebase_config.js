// Firebase Configuration
const firebaseConfig = {
    apiKey: "AIzaSyCerPj2te-b2c5v1RWaaOtmMHIS_OW8SPc",
    authDomain: "ailearn-279db.firebaseapp.com",
    projectId: "ailearn-279db",
    storageBucket: "ailearn-279db.firebasestorage.app",
    messagingSenderId: "934139105845",
    appId: "1:934139105845:web:a773566bd770a134dc577c",
    measurementId: "G-HSX9PFH2DW",
};

let firebaseApp = null;
let firebaseAuth = null;
let firestore = null;

try {
    if (typeof firebase !== 'undefined') {
        firebaseApp = firebase.initializeApp(firebaseConfig);
        firebaseAuth = firebase.auth();
        firebaseAuth.useDeviceLanguage();
        console.log('[Firebase] Initialized');
    }
} catch (e) {
    console.warn('[Firebase] Not initialized:', e.message);
}

function isFirebaseAvailable() {
    return firebaseAuth !== null;
}

async function firebaseEmailSignUp(email, password, name, role) {
    if (!isFirebaseAvailable()) return null;
    try {
        const result = await firebaseAuth.createUserWithEmailAndPassword(email, password);
        const user = result.user;
        await user.updateProfile({ displayName: name });
        const idToken = await user.getIdToken();
        const apiResult = await apiRequest('/api/auth/firebase/register', 'POST', {
            idToken, name, email, role,
        });
        return apiResult;
    } catch (error) {
        return { success: false, message: error.message };
    }
}

async function firebaseEmailSignIn(email, password) {
    if (!isFirebaseAvailable()) return null;
    try {
        const result = await firebaseAuth.signInWithEmailAndPassword(email, password);
        const idToken = await result.user.getIdToken();
        return await apiRequest('/api/auth/firebase/login', 'POST', { idToken });
    } catch (error) {
        return { success: false, message: error.message };
    }
}

async function firebaseGoogleSignIn() {
    if (!isFirebaseAvailable()) return null;
    try {
        const provider = new firebase.auth.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: 'select_account' });
        const result = await firebaseAuth.signInWithPopup(provider);
        const user = result.user;
        const idToken = await user.getIdToken();

        let apiResult = await apiRequest('/api/auth/firebase/login', 'POST', { idToken });

        if (!apiResult.success && apiResult.registerRequired) {
            apiResult = await apiRequest('/api/auth/firebase/register', 'POST', {
                idToken, name: user.displayName, email: user.email, role: 'student',
            });
        }
        return apiResult;
    } catch (error) {
        return { success: false, message: error.message };
    }
}

async function firebaseLogout() {
    if (isFirebaseAvailable()) {
        try { await firebaseAuth.signOut(); } catch (e) {}
    }
    await apiRequest('/api/auth/logout', 'POST');
}

function onFirebaseAuthStateChanged(callback) {
    if (!isFirebaseAvailable()) { callback(null); return; }
    firebaseAuth.onAuthStateChanged(user => { callback(user); });
}
