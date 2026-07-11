// =====================================================================
// fetch_music.js — zieht das Spotify-Skelett in music.json
// =====================================================================
// Läuft mit Node 18+ (globales fetch, keine Abhängigkeiten) oder Deno.
//
//   Aufruf:
//     SPOTIFY_CLIENT_ID=xxx SPOTIFY_CLIENT_SECRET=yyy node fetch_music.js
//
// Holt automatisch (das "Skelett"):
//   Titel · Veröffentlichungsdatum · Album · Cover-URL · Spotify-Link
// Lässt unangetastet (deine "Seele", manuell gepflegt):
//   lyrics · note · genre  — bestehende Werte in music.json werden
//   beim erneuten Ziehen BEWAHRT (Merge über die Spotify-Track-ID).
// =====================================================================

const fs = require('fs');
const path = require('path');

// Chaos ex Ordo (aus der bestehenden Seite). Per Env/Arg überschreibbar.
const ARTIST_ID =
  process.env.SPOTIFY_ARTIST_ID ||
  process.argv[2] ||
  '3LQ3n2HV0Dm8On9TpZfQSS';

const OUT = path.join(__dirname, 'music.json');
const ID = process.env.SPOTIFY_CLIENT_ID;
const SECRET = process.env.SPOTIFY_CLIENT_SECRET;

if (!ID || !SECRET) {
  console.error('Fehlt: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (Env-Variablen).');
  process.exit(1);
}

// ---- Token (Client-Credentials-Flow) --------------------------------
async function getToken() {
  const res = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Authorization': 'Basic ' + Buffer.from(ID + ':' + SECRET).toString('base64'),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
  });
  if (!res.ok) throw new Error('Token fehlgeschlagen: ' + res.status);
  return (await res.json()).access_token;
}

async function api(token, url) {
  const res = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
  if (!res.ok) throw new Error(url + ' → ' + res.status);
  return res.json();
}

// ---- alle Alben/Singles → alle Tracks -------------------------------
async function allAlbums(token) {
  const out = [];
  let url = `https://api.spotify.com/v1/artists/${ARTIST_ID}/albums?include_groups=album,single&limit=50&market=DE`;
  while (url) {
    const page = await api(token, url);
    out.push(...page.items);
    url = page.next;
  }
  // Duplikate (gleicher Titel) grob rausfiltern
  const seen = new Set();
  return out.filter(a => (seen.has(a.name) ? false : seen.add(a.name)));
}

async function tracksOfAlbum(token, album) {
  const page = await api(token, `https://api.spotify.com/v1/albums/${album.id}/tracks?limit=50&market=DE`);
  return page.items.map(t => ({
    id: t.id,
    title: t.name,
    releaseDate: album.release_date,          // Skelett
    album: album.name,                        // Skelett
    cover: (album.images && album.images[0] && album.images[0].url) || '', // Skelett (URL)
    spotifyUrl: t.external_urls.spotify,       // Skelett
    genre: [],                                 // Seele — manuell
    lyrics: '',                                // Seele — manuell
    note: '',                                  // Seele — manuell
  }));
}

// ---- Merge: bewahrt manuell gepflegte Felder ------------------------
function mergeManual(fresh, oldList) {
  const old = new Map((oldList || []).map(s => [s.id || s.title, s]));
  return fresh.map(s => {
    const prev = old.get(s.id) || old.get(s.title);
    if (!prev) return s;
    return {
      ...s,
      genre:  (prev.genre && prev.genre.length) ? prev.genre : s.genre,
      lyrics: prev.lyrics || s.lyrics,
      note:   prev.note   || s.note,
    };
  });
}

(async () => {
  try {
    const token = await getToken();
    const albums = await allAlbums(token);
    let songs = [];
    for (const a of albums) songs.push(...await tracksOfAlbum(token, a));

    // neueste zuerst
    songs.sort((a, b) => (b.releaseDate || '').localeCompare(a.releaseDate || ''));

    // bestehende manuelle Pflege bewahren
    let oldList = [];
    if (fs.existsSync(OUT)) {
      try { oldList = JSON.parse(fs.readFileSync(OUT, 'utf8')); } catch (_) {}
    }
    songs = mergeManual(songs, oldList);

    fs.writeFileSync(OUT, JSON.stringify(songs, null, 2));
    console.log(`✓ ${songs.length} Songs → ${OUT}`);
  } catch (e) {
    console.error('Fehler:', e.message);
    process.exit(1);
  }
})();
