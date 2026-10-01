const fs = require('node:fs');
const path = require('node:path');
const libs = path.resolve(process.argv[2] || path.join(__dirname, '..', 'node_modules'));
const {initializeTestEnvironment, assertSucceeds, assertFails} = require(path.join(libs, '@firebase/rules-unit-testing'));
const {doc, setDoc, getDoc, getDocs, collection, serverTimestamp} = require(path.join(libs, 'firebase/firestore'));
(async () => {
  const env = await initializeTestEnvironment({projectId: 'demo-shortory', firestore: {host: '127.0.0.1', port: 8180, rules: fs.readFileSync(path.join(__dirname, '..', 'firestore.rules'), 'utf8')}});
  try {
    await env.clearFirestore();
    await env.withSecurityRulesDisabled(async ctx => {
      await setDoc(doc(ctx.firestore(), 'users/alice/shorts/sample'), {owner_uid: 'alice', title: 'Private short'});
    });
    const alice = env.authenticatedContext('alice', {email: 'alice@users.shortory.invalid'}).firestore();
    const bob = env.authenticatedContext('bob', {email: 'bobby@users.shortory.invalid'}).firestore();
    const guest = env.unauthenticatedContext().firestore();
    await assertSucceeds(getDoc(doc(alice, 'users/alice/shorts/sample')));
    await assertSucceeds(getDocs(collection(alice, 'users/alice/shorts')));
    await assertFails(getDoc(doc(bob, 'users/alice/shorts/sample')));
    await assertFails(getDocs(collection(bob, 'users/alice/shorts')));
    await assertFails(getDoc(doc(guest, 'users/alice/shorts/sample')));
    await assertFails(setDoc(doc(alice, 'users/alice/shorts/forged'), {owner_uid: 'alice'}));
    const profile = {login_id: 'alice', display_name: 'alice', updated_at: serverTimestamp()};
    await assertSucceeds(setDoc(doc(alice, 'users/alice'), profile));
    await assertFails(setDoc(doc(bob, 'users/alice'), profile));
    await assertFails(setDoc(doc(alice, 'users/alice'), {...profile, password: 'never-store-me'}));
    await assertFails(setDoc(doc(alice, 'users/alice'), {...profile, login_id: 'another'}));
    console.log('PASS: 10 Firestore rules checks (owner access, account isolation, anonymous denial, server-only records, profile validation).');
  } finally { await env.cleanup(); }
})().catch(e => { console.error(e.code || e.message); process.exitCode = 1; });
