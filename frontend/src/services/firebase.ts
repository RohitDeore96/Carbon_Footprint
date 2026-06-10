/**
 * Firebase initialization and authentication service.
 * Provides anonymous authentication so each user gets a unique identity.
 * Falls back gracefully if Firebase is unavailable.
 */

import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, onAuthStateChanged } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
};

// Validate required Firebase config before initialization
const missingFields = Object.entries(firebaseConfig)
  .filter(([, value]) => !value)
  .map(([key]) => key);

if (missingFields.length > 0) {
  console.warn(
    `Firebase config missing: ${missingFields.join(', ')}. ` +
    'Set VITE_FIREBASE_* environment variables for full functionality.'
  );
}

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

/**
 * Sign in anonymously and return the user's UID.
 * Falls back to a generated ID if sign-in fails.
 */
export async function signInAnonymouslyAndGetUser(): Promise<{ uid: string }> {
  try {
    const credential = await signInAnonymously(auth);
    return { uid: credential.user.uid };
  } catch (error) {
    console.warn('Firebase anonymous sign-in failed, using fallback ID:', error);
    const fallbackUid = `fallback-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    return { uid: fallbackUid };
  }
}

/**
 * Subscribe to authentication state changes.
 * Returns an unsubscribe function.
 */
export function onAuthChange(callback: (uid: string | null) => void): () => void {
  return onAuthStateChanged(auth, (user) => {
    callback(user ? user.uid : null);
  });
}
