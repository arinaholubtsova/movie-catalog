import React, { useEffect, useRef, useState } from 'react';

type Movie = { id: number; title: string; year: number; genres: string[]; avg_rating: number; rating_count: number; poster_url?: string | null; overview?: string; keywords?: string; external_id?: string | null; actors?: string[]; directors?: string[] };
type Recommendation = { movie: Movie; score: number; reason: string };
type Event = { id: number; movie_id: number; movie: Movie | null; type: string; value: number | null; timestamp: string };
type Section = 'catalog' | 'favorites' | 'watchlist' | 'watched' | 'history' | 'recommendations' | 'account' | 'admin';
type ListName = 'favorites' | 'watchlist' | 'watched';
type MovieState = { rating: number | null; lists: Record<ListName, boolean> };
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const CATALOG_GENRES = ['Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Horror', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller'];
const nav: Array<[Section, string, string]> = [
  ['catalog', 'Каталог', '▦'], ['recommendations', 'Для вас', '✦'], ['favorites', 'Улюблені', '♡'],
  ['watchlist', 'Хочу подивитися', '▤'], ['watched', 'Переглянуті', '✓'], ['history', 'Історія', '◷'], ['account', 'Профіль', '♙'],
];
const listLabels: Record<ListName, string> = { favorites: 'Улюблене', watchlist: 'До перегляду', watched: 'Переглянуто' };
const eventLabels: Record<string, string> = {
  rating_set: 'Встановлено оцінку', favorites_added: 'Додано до улюблених', favorites_removed: 'Видалено з улюблених',
  watchlist_added: 'Додано до списку «Хочу подивитися»', watchlist_removed: 'Видалено зі списку «Хочу подивитися»',
  watched_added: 'Позначено як переглянутий', watched_removed: 'Знято позначку «Переглянуто»',
};

function Poster({ movie, className = '' }: { movie: Movie; className?: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [movie.poster_url]);
  return <div className={`poster ${className}`}>
    {movie.poster_url && !failed ? <img src={movie.poster_url} alt={`Постер фільму «${movie.title}»`} onError={() => setFailed(true)} />
      : <div className="poster-fallback"><span>✦</span><strong>{movie.title}</strong><small>{movie.year}</small></div>}
  </div>;
}

function MovieCard({ movie, onOpen, extra }: { movie: Movie; onOpen: (id: number) => void; extra?: React.ReactNode }) {
  return <article className="movie-card"><button className="card-open" type="button" onClick={() => onOpen(movie.id)} aria-label={`Відкрити ${movie.title}`}>
    <Poster movie={movie} /><div className="card-shade" /><div className="card-info"><div className="card-meta"><span>{movie.year}</span><span className="rating-pill">★ {movie.avg_rating.toFixed(1)} <small>/ 10</small></span></div><h3>{movie.title}</h3><p>{movie.genres.slice(0, 2).join(' · ') || 'Фільм'}</p></div>
  </button>{extra && <div className="card-extra">{extra}</div>}</article>;
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [role, setRole] = useState(localStorage.getItem('role') || '');
  const [section, setSection] = useState<Section>('catalog');
  const [items, setItems] = useState<Movie[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [history, setHistory] = useState<Event[]>([]);
  const [selected, setSelected] = useState<Movie | null>(null);
  const [similar, setSimilar] = useState<Array<{ movie: Movie; score: number }>>([]);
  const [movieState, setMovieState] = useState<MovieState | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [genre, setGenre] = useState('');
  const [year, setYear] = useState('');
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [rating, setRating] = useState('');
  const [sort, setSort] = useState('title');
  const [genres, setGenres] = useState<Array<{ id: number; name: string }>>([]);
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState<'success' | 'error' | 'info'>('info');
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'register' | null>(null);
  const [accountEmail, setAccountEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const emptyMovieForm = () => ({ title: '', year: String(new Date().getFullYear()), overview: '', keywords: '', poster_url: '', external_id: '', genre_ids: [] as number[], actors: '', directors: '' });
  const [movieForm, setMovieForm] = useState(emptyMovieForm);
  const [genreName, setGenreName] = useState('');
  const [mobileMore, setMobileMore] = useState(false);
  const refreshSerial = useRef(0);

  const invalidYear = [year, yearFrom, yearTo].some(value => value !== '' && (!Number.isInteger(Number(value)) || Number(value) < 1888 || Number(value) > 2200));
  const filterError = invalidYear ? 'Рік має бути цілим числом від 1888 до 2200.'
    : yearFrom && yearTo && Number(yearFrom) > Number(yearTo) ? '«Рік від» не може бути більшим за «Рік до».'
    : rating !== '' && (!Number.isFinite(Number(rating)) || Number(rating) < 0 || Number(rating) > 10) ? 'Мінімальний рейтинг має бути від 0 до 10.' : '';
  const activeFilterCount = [q, genre, year, yearFrom, yearTo, rating].filter(Boolean).length;

  function notify(text: string, tone: 'success' | 'error' | 'info' = 'info') { setMessage(text); setMessageTone(tone); }
  function resetFilters() { setQ(''); setGenre(''); setYear(''); setYearFrom(''); setYearTo(''); setRating(''); setSort('title'); setPage(1); }

  async function request(path: string, options: RequestInit = {}) {
    const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      if (response.status === 401 && token && path !== '/auth/login' && path !== '/auth/logout') {
        localStorage.removeItem('token'); localStorage.removeItem('role'); setToken(''); setRole(''); setSection('catalog'); setSelected(null);
        throw new Error('Сесію завершено. Увійдіть знову, щоб продовжити.');
      }
      if (typeof error.detail === 'string') {
        const known: Record<string, string> = { 'Invalid credentials': 'Неправильний email або пароль.', 'Email already registered': 'Цей email уже зареєстрований.' };
        throw new Error(known[error.detail] || error.detail);
      }
      if (Array.isArray(error.detail)) throw new Error(error.detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.[item.loc.length - 1] || 'Поле'}: ${item.msg || 'некоректне значення'}`).join('; '));
      throw new Error(`Помилка запиту (${response.status}).`);
    }
    return response.status === 204 ? null : response.json();
  }

  async function refresh() {
    const serial = ++refreshSerial.current;
    try {
      if (section === 'catalog' || section === 'admin') {
        if (filterError) { setLoading(false); return; }
        setLoading(true);
        const params = new URLSearchParams({ page: String(page), sort });
        if (q) params.set('q', q); if (genre) params.set('genre', genre); if (year) params.set('year', year);
        if (yearFrom) params.set('year_from', yearFrom); if (yearTo) params.set('year_to', yearTo); if (rating) params.set('min_rating', rating);
        const result = await request(`/movies?${params}`); if (serial === refreshSerial.current) { setItems(result.items); setTotal(result.total); }
      } else if (section === 'recommendations') { setLoading(true); const result = await request('/me/recommendations?k=10'); if (serial === refreshSerial.current) setRecommendations(result); }
      else if (section === 'history') { setLoading(true); const result = await request('/me/history'); if (serial === refreshSerial.current) setHistory(result); }
      else if (section === 'account') { const profile = await request('/auth/me'); setAccountEmail(current => current || profile.email); }
      else { setLoading(true); const result = await request(`/me/${section}`); if (serial === refreshSerial.current) setItems(result); }
    } catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
    finally { if (serial === refreshSerial.current) setLoading(false); }
  }
  useEffect(() => {
    if (section !== 'account') setLoading(true);
    const timer = window.setTimeout(() => void refresh(), q ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [section, page, q, genre, year, yearFrom, yearTo, rating, sort, token]);
  useEffect(() => { request('/genres').then(setGenres).catch(() => {}); }, []);
  useEffect(() => { setMessage(''); }, [page, q, genre, year, yearFrom, yearTo, rating, sort]);

  async function authenticate(kind: 'login' | 'register') {
    if (!email.trim() || !password) { notify('Введіть email і пароль.', 'error'); return; }
    if (kind === 'register' && password.length < 8) { notify('Пароль має містити щонайменше 8 символів.', 'error'); return; }
    try {
      const data = await request(`/auth/${kind}`, { method: 'POST', body: JSON.stringify({ email: email.trim(), password }) });
      if (kind === 'register') { setAuthMode('login'); notify('Реєстрацію завершено. Тепер увійдіть.', 'success'); return; }
      localStorage.setItem('token', data.access_token); localStorage.setItem('role', data.role);
      setToken(data.access_token); setRole(data.role); setAuthMode(null); setPassword(''); setAccountEmail(''); notify('Вхід виконано', 'success');
    } catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
  }
  async function logout() {
    try { await request('/auth/logout', { method: 'POST' }); } catch { /* local session still closes */ }
    localStorage.removeItem('token'); localStorage.removeItem('role'); setToken(''); setRole(''); setSection('catalog'); setSelected(null); setAccountEmail(''); setMovieState(null);
  }
  async function action(path: string, method: string, body?: unknown) {
    try {
      const result = await request(path, { method, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
      notify('Зміни збережено', 'success'); await refresh();
      if (selected && !(method === 'DELETE' && path.startsWith('/admin/movies/'))) {
        const updated = await request(`/movies/${selected.id}`);
        setSelected(current => current?.id === selected.id ? updated : current);
        if (token) {
          const state = await request(`/me/movie-state/${selected.id}`);
          setMovieState(current => current && state ? state : current);
        }
      }
      return result;
    } catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
  }
  async function openMovie(id: number) {
    try {
      const [movie, related, state] = await Promise.all([request(`/movies/${id}`), request(`/movies/${id}/similar`), token ? request(`/me/movie-state/${id}`) : Promise.resolve(null)]);
      setSelected(movie); setSimilar(related); setMovieState(state); window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
  }
  function navigate(name: Section) { setSection(name); setSelected(null); setMessage(''); setMobileMore(false); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  async function saveEmail(event: React.FormEvent) { event.preventDefault(); const result = await action('/me/email', 'PUT', { email: accountEmail }); if (result) setAccountEmail(result.email); }
  async function savePassword(event: React.FormEvent) { event.preventDefault(); if (await action('/me/password', 'PUT', { current_password: currentPassword, new_password: newPassword }) !== undefined) { setCurrentPassword(''); setNewPassword(''); } }
  async function removeAccount(event: React.FormEvent) {
    event.preventDefault(); try { await request('/me/account', { method: 'DELETE', body: JSON.stringify({ password: deletePassword, confirmation: deleteConfirmation }) }); await logout(); notify('Обліковий запис видалено', 'success'); }
    catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
  }
  async function createMovie(event: React.FormEvent) {
    event.preventDefault(); const result = await action('/admin/movies', 'POST', { ...movieForm, year: Number(movieForm.year), poster_url: movieForm.poster_url || null, external_id: movieForm.external_id || null, actors: movieForm.actors.split(',').map(s => s.trim()).filter(Boolean), directors: movieForm.directors.split(',').map(s => s.trim()).filter(Boolean) });
    if (result) setMovieForm(emptyMovieForm());
  }
  async function synchronize() {
    try { const result = await request('/admin/sync', { method: 'POST' }); notify(`Створено: ${result.created}, оновлено: ${result.updated}, пропущено: ${result.skipped}`, 'success'); await refresh(); }
    catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
  }

  const title = section === 'admin' ? 'Керування каталогом' : nav.find(([name]) => name === section)?.[1] || 'Каталог';
  const featured = items.find(item => item.poster_url) || items[0];

  return <div className="app-shell">
    <header className="site-header"><div className="header-inner">
      <nav className="desktop-nav" aria-label="Основна навігація">{nav.filter(([name]) => token || name === 'catalog').slice(0, 5).map(([name, label]) => <button key={name} className={section === name && !selected ? 'nav-active' : ''} onClick={() => navigate(name)}>{label}</button>)}{role === 'admin' && <button className={section === 'admin' ? 'nav-active' : ''} onClick={() => navigate('admin')}>Адмін</button>}</nav>
      <div className="header-user">{token ? <><span className="role-chip">{role === 'admin' ? 'Адміністратор' : 'Глядач'}</span><button className="text-button" onClick={() => navigate('account')}>Профіль</button><button className="outline-button" onClick={() => void logout()}>Вийти</button></> : <div className="auth-tabs" role="tablist" aria-label="Обліковий запис"><button type="button" role="tab" aria-selected={authMode === 'login'} className={authMode === 'login' ? 'tab-active' : ''} onClick={() => { setAuthMode('login'); setMessage(''); }}>Увійти</button><button type="button" role="tab" aria-selected={authMode === 'register'} className={authMode === 'register' ? 'tab-active' : ''} onClick={() => { setAuthMode('register'); setMessage(''); }}>Зареєструватися</button></div>}</div>
    </div></header>

    <div className="page-wrap">
      {message && <div role={messageTone === 'error' ? 'alert' : 'status'} className={`toast toast-${messageTone}`}><span>{message}</span><button aria-label="Закрити повідомлення" onClick={() => setMessage('')}>×</button></div>}
      {!token && authMode && <section className="auth-panel" aria-label="Обліковий запис"><div><span className="eyebrow">ОБЛІКОВИЙ ЗАПИС</span><h2>{authMode === 'login' ? 'З поверненням!' : 'Приєднуйтесь до Кіносвіту'}</h2><p>{authMode === 'login' ? 'Увійдіть, щоб зберігати фільми й отримувати персональні рекомендації.' : 'Створіть профіль для власних списків, оцінок і добірок.'}</p></div><form onSubmit={event => { event.preventDefault(); void authenticate(authMode); }}><label>Email<input type="email" required autoComplete="email" placeholder="name@example.com" aria-label="Email" value={email} onChange={e => setEmail(e.target.value)} /></label><label>Пароль<input type="password" required minLength={authMode === 'register' ? 8 : undefined} maxLength={128} autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} placeholder={authMode === 'register' ? 'Від 8 символів' : 'Ваш пароль'} aria-label="Пароль" value={password} onChange={e => setPassword(e.target.value)} /></label><button className="primary-button" type="submit">{authMode === 'login' ? 'Увійти →' : 'Створити обліковий запис →'}</button></form></section>}

      {selected ? <>
        <button className="back-link" onClick={() => setSelected(null)}>← Повернутися до {title.toLowerCase()}</button>
        <section className="detail-layout"><Poster movie={selected} className="detail-poster" /><div className="detail-content"><span className="eyebrow">ФІЛЬМ · {selected.year}</span><h1>{selected.title}</h1><div className="detail-chips"><span className="rating-pill">★ {selected.avg_rating.toFixed(1)} / 10</span><span>{selected.rating_count} оцінок</span>{selected.genres.map(g => <span key={g}>{g}</span>)}</div><p className="detail-overview">{selected.overview || 'Опис цього фільму ще не додано.'}</p><div className="film-facts"><div><small>Режисери</small><strong>{selected.directors?.join(', ') || '—'}</strong></div><div><small>Актори</small><strong>{selected.actors?.join(', ') || '—'}</strong></div></div>
          {token ? <div className="interaction-panel"><div className="panel-heading"><h2>Ваша взаємодія</h2><p>Оцініть за шкалою 1–5. У каталозі середній рейтинг показано за шкалою 0–10.</p></div><div className="rating-control"><span>Моя оцінка</span><div className="stars" role="group" aria-label="Моя оцінка від 1 до 5">{[1, 2, 3, 4, 5].map(n => <button type="button" key={n} className={n <= (movieState?.rating || 0) ? 'star-on' : ''} aria-label={`Оцінити на ${n} з 5`} aria-pressed={movieState?.rating === n} onClick={() => void action(`/me/ratings/${selected.id}`, 'PUT', { value: n })}>★</button>)}</div><strong>{movieState?.rating ? `${movieState.rating} / 5` : 'Без оцінки'}</strong></div><div className="list-actions">{(['favorites', 'watchlist', 'watched'] as ListName[]).map(name => <button type="button" key={name} className={movieState?.lists[name] ? 'list-active' : ''} aria-pressed={!!movieState?.lists[name]} onClick={() => void action(`/me/${name}/${selected.id}`, movieState?.lists[name] ? 'DELETE' : 'PUT')}><span>{name === 'favorites' ? '♡' : name === 'watchlist' ? '▤' : '✓'}</span>{listLabels[name]}{movieState?.lists[name] && <b>✓</b>}</button>)}</div></div> : <div className="signin-hint">Увійдіть, щоб оцінити фільм і додати його до своїх списків.</div>}
        </div></section>
        <section className="content-section"><div className="section-heading"><div><span className="eyebrow">МОЖЕ СПОДОБАТИСЯ</span><h2>Схожі фільми</h2></div></div><div className="poster-grid">{similar.map(item => <MovieCard key={item.movie.id} movie={item.movie} onOpen={openMovie} extra={<span>Подібність {Math.round(item.score * 100)}%</span>} />)}</div></section>
        {role === 'admin' && <section className="admin-card"><h2>Редагувати фільм</h2><p>Змініть основні дані, контентні ознаки та учасників фільму.</p><form className="form-grid" onSubmit={e => { e.preventDefault(); void action(`/admin/movies/${selected.id}`, 'PATCH', { title: selected.title, year: selected.year, overview: selected.overview || '', keywords: selected.keywords || '', poster_url: selected.poster_url || null, external_id: selected.external_id || null, actors: selected.actors || [], directors: selected.directors || [], genre_ids: selected.genres.map(name => genres.find(item => item.name === name)?.id).filter((id): id is number => id !== undefined) }); }}><label>Назва<input required value={selected.title} onChange={e => setSelected({ ...selected, title: e.target.value })} /></label><label>Рік<input required min="1888" max="2200" type="number" value={selected.year} onChange={e => setSelected({ ...selected, year: Number(e.target.value) })} /></label><label className="wide">URL постера<input type="text" value={selected.poster_url || ''} onChange={e => setSelected({ ...selected, poster_url: e.target.value })} placeholder="https://… або /posters/…" /></label><label className="wide">Опис<textarea value={selected.overview || ''} onChange={e => setSelected({ ...selected, overview: e.target.value })} /></label><label>Ключові слова<input value={selected.keywords || ''} onChange={e => setSelected({ ...selected, keywords: e.target.value })} placeholder="Через кому" /></label><label>Зовнішній ID<input value={selected.external_id || ''} onChange={e => setSelected({ ...selected, external_id: e.target.value })} /></label><label>Актори<input value={(selected.actors || []).join(', ')} onChange={e => setSelected({ ...selected, actors: e.target.value.split(',').map(value => value.trim()).filter(Boolean) })} placeholder="Через кому" /></label><label>Режисери<input value={(selected.directors || []).join(', ')} onChange={e => setSelected({ ...selected, directors: e.target.value.split(',').map(value => value.trim()).filter(Boolean) })} placeholder="Через кому" /></label><label className="wide">Жанри<select multiple value={selected.genres} onChange={e => setSelected({ ...selected, genres: Array.from(e.target.selectedOptions, option => option.value) })}>{genres.map(g => <option key={g.id} value={g.name}>{g.name}</option>)}</select><small>Для вибору кількох жанрів утримуйте Ctrl.</small></label><button className="primary-button" type="submit">Зберегти всі зміни</button></form><button className="danger-link" onClick={() => { if (window.confirm(`Видалити фільм «${selected.title}»? Цю дію неможливо скасувати.`)) { void action(`/admin/movies/${selected.id}`, 'DELETE'); setSelected(null); } }}>Видалити фільм</button></section>}
      </> : <main>
        {section === 'catalog' && !q && !genre && !year && !yearFrom && !yearTo && !rating && page === 1 && featured && <section className="hero"><div className="hero-backdrop" style={{ backgroundImage: `url('${featured.poster_url || ''}')` }} /><div className="hero-copy"><span className="eyebrow">ВІДКРИВАЙТЕ ІСТОРІЇ</span><h1>Ваш наступний<br /><em>улюблений фільм</em><br />вже тут.</h1><p>Знаходьте кіно за настроєм, зберігайте у власні списки та відкривайте рекомендації, створені для вас.</p><div className="hero-actions"><button className="primary-button" onClick={() => document.getElementById('catalog-results')?.scrollIntoView({ behavior: 'smooth' })}>Дивитися каталог ↗</button>{token && <button className="outline-button" onClick={() => navigate('recommendations')}>Мої рекомендації ✦</button>}</div></div><div className="hero-feature"><Poster movie={featured} /><span>У центрі уваги <strong>{featured.title}</strong></span></div></section>}

        <section className="content-section" id="catalog-results"><div className="section-heading"><div><span className="eyebrow">{section === 'catalog' ? 'КОЛЕКЦІЯ' : 'ВАШ ПРОСТІР'}</span><h2>{title}</h2><p>{section === 'catalog' ? `${total} фільмів для відкриття` : section === 'recommendations' ? 'Добірка на основі ваших оцінок і збережених фільмів' : section === 'favorites' || section === 'watchlist' || section === 'watched' ? 'Фільми, які ви зберегли у своєму профілі' : ''}</p></div>{section === 'catalog' && <span className="count-badge">{total} фільмів</span>}</div>
          {(section === 'catalog' || section === 'admin') && <div className="filter-panel"><div className="filter-main"><label className="search-field"><span>⌕</span><input aria-label="Назва або ключове слово" placeholder="Пошук за назвою або ключовим словом..." value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /></label><select aria-label="Жанр" value={genre} onChange={e => { setGenre(e.target.value); setPage(1); }}><option value="">Усі жанри</option>{CATALOG_GENRES.map(name => <option key={name}>{name}</option>)}</select><select aria-label="Сортування" value={sort} onChange={e => setSort(e.target.value)}><option value="title">За назвою</option><option value="year">За роком</option><option value="rating">За рейтингом</option></select></div><div className="filter-more"><input type="number" min="1888" max="2200" aria-label="Точний рік" placeholder="Точний рік" value={year} onChange={e => { const value = e.target.value; setYear(value); if (value) { setYearFrom(''); setYearTo(''); } setPage(1); }} /><input type="number" min="1888" max="2200" aria-label="Рік від" placeholder="Рік від" value={yearFrom} onChange={e => { const value = e.target.value; setYearFrom(value); if (value) setYear(''); setPage(1); }} /><input type="number" min="1888" max="2200" aria-label="Рік до" placeholder="Рік до" value={yearTo} onChange={e => { const value = e.target.value; setYearTo(value); if (value) setYear(''); setPage(1); }} /><input type="number" min="0" max="10" step="0.1" aria-label="Мінімальний рейтинг від 0 до 10" placeholder="Рейтинг від 0 до 10" value={rating} onChange={e => { setRating(e.target.value); setPage(1); }} /><button type="button" className="filter-reset" onClick={resetFilters} disabled={!activeFilterCount && sort === 'title'}>Скинути{activeFilterCount ? ` (${activeFilterCount})` : ''}</button></div>{filterError && <p role="alert" className="filter-error">{filterError}</p>}</div>}
          {section === 'account' ? <div className="account-grid"><form className="admin-card" onSubmit={saveEmail}><span className="form-icon">✉</span><h3>Електронна адреса</h3><p>Адреса для входу у ваш профіль.</p><label>Новий email<input type="email" required aria-label="Новий email" value={accountEmail} onChange={e => setAccountEmail(e.target.value)} /></label><button className="primary-button" type="submit">Зберегти email</button></form><form className="admin-card" onSubmit={savePassword}><span className="form-icon">◇</span><h3>Пароль</h3><p>Новий пароль має містити від 8 символів.</p><label>Поточний пароль<input type="password" required aria-label="Поточний пароль" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label><label>Новий пароль<input type="password" required minLength={8} aria-label="Новий пароль" value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label><button className="primary-button" type="submit">Змінити пароль</button></form><form className="admin-card danger-card" onSubmit={removeAccount}><span className="form-icon">×</span><h3>Видалити профіль</h3><p>Оцінки, списки та історія будуть видалені. Введіть пароль і DELETE.</p><label>Пароль<input type="password" required aria-label="Пароль для видалення" value={deletePassword} onChange={e => setDeletePassword(e.target.value)} /></label><label>Підтвердження<input required aria-label="Підтвердження DELETE" placeholder="DELETE" value={deleteConfirmation} onChange={e => setDeleteConfirmation(e.target.value)} /></label><button className="danger-button" type="submit" disabled={deleteConfirmation !== 'DELETE'}>Видалити профіль</button></form></div>
            : section === 'history' ? loading ? <div className="loading-state" role="status">Завантажуємо історію…</div> : <div className="history-list">{history.length ? history.map(event => <div key={event.id}>{event.movie ? <button className="history-movie" onClick={() => void openMovie(event.movie!.id)}><Poster movie={event.movie} /><span><strong>{event.movie.title}</strong><small>{event.movie.year}</small></span></button> : <strong>Видалений фільм #{event.movie_id}</strong>}<span className="history-action"><b>{eventLabels[event.type] || event.type}</b>{event.type === 'rating_set' && event.value !== null ? ` · ${event.value}/5` : ''}</span><time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString('uk-UA')}</time></div>) : <div className="empty-state"><span>◷</span><h3>Історія поки порожня</h3><p>Оцініть або збережіть фільм, щоб побачити свої дії тут.</p></div>}</div>
            : loading ? <div className="loading-state" role="status">Завантажуємо фільми…</div> : <div className="poster-grid">{section === 'recommendations' ? recommendations.map(item => <MovieCard key={item.movie.id} movie={item.movie} onOpen={openMovie} extra={<span>{item.reason}</span>} />) : items.map(movie => <MovieCard key={movie.id} movie={movie} onOpen={openMovie} />)}</div>}
          {!loading && section !== 'account' && section !== 'history' && (section === 'recommendations' ? recommendations.length === 0 : items.length === 0) && <div className="empty-state"><span>✦</span><h3>Тут поки немає фільмів</h3><p>{section === 'catalog' ? 'Спробуйте змінити параметри пошуку.' : 'Відкрийте каталог і збережіть фільми, які вас зацікавили.'}</p>{section !== 'catalog' && <button className="primary-button" onClick={() => navigate('catalog')}>До каталогу →</button>}</div>}
          {(section === 'catalog' || section === 'admin') && <div className="pager"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Назад</button><span>Сторінка {page} з {Math.max(1, Math.ceil(total / 20))}</span><button disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>Далі →</button></div>}
        </section>
        {section === 'admin' && <section className="admin-area">
          <div className="admin-card"><span className="eyebrow">ДОВІДНИК</span><h2>Жанри</h2><div className="genre-list">{genres.map(g => <span key={g.id}>{g.name}<button onClick={async () => { const name = window.prompt('Нова назва жанру', g.name); if (name) { await action(`/admin/genres/${g.id}`, 'PUT', { name }); setGenres(await request('/genres')); } }}>Змінити</button><button aria-label={`Видалити жанр ${g.name}`} onClick={async () => { if (window.confirm(`Видалити жанр «${g.name}»?`)) { await action(`/admin/genres/${g.id}`, 'DELETE'); setGenres(await request('/genres')); } }}>×</button></span>)}</div><div className="inline-form"><input aria-label="Назва жанру" value={genreName} onChange={e => setGenreName(e.target.value)} placeholder="Назва жанру" /><button className="primary-button" disabled={!genreName.trim()} onClick={async () => { const result = await action('/admin/genres', 'POST', { name: genreName }); if (result) { setGenres(await request('/genres')); setGenreName(''); } }}>Додати жанр</button></div></div>
          <div className="admin-card"><span className="eyebrow">КАТАЛОГ</span><h2>Додати фільм</h2><form className="form-grid" onSubmit={createMovie}><label>Назва<input required value={movieForm.title} onChange={e => setMovieForm({ ...movieForm, title: e.target.value })} /></label><label>Рік<input required min="1888" max="2200" type="number" value={movieForm.year} onChange={e => setMovieForm({ ...movieForm, year: e.target.value })} /></label><label className="wide">URL постера<input value={movieForm.poster_url} onChange={e => setMovieForm({ ...movieForm, poster_url: e.target.value })} placeholder="https://… або /posters/…" /></label><label className="wide">Опис<textarea value={movieForm.overview} onChange={e => setMovieForm({ ...movieForm, overview: e.target.value })} /></label><label>Ключові слова<input value={movieForm.keywords} onChange={e => setMovieForm({ ...movieForm, keywords: e.target.value })} placeholder="Через кому" /></label><label>Зовнішній ID<input value={movieForm.external_id} onChange={e => setMovieForm({ ...movieForm, external_id: e.target.value })} /></label><label>Актори<input value={movieForm.actors} onChange={e => setMovieForm({ ...movieForm, actors: e.target.value })} placeholder="Через кому" /></label><label>Режисери<input value={movieForm.directors} onChange={e => setMovieForm({ ...movieForm, directors: e.target.value })} placeholder="Через кому" /></label><label>Жанри<select multiple value={movieForm.genre_ids.map(String)} onChange={e => setMovieForm({ ...movieForm, genre_ids: Array.from(e.target.selectedOptions, option => Number(option.value)) })}>{genres.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select><small>Для вибору кількох жанрів утримуйте Ctrl.</small></label><button className="primary-button" type="submit">Створити фільм</button></form><button className="outline-button sync-button" onClick={() => void synchronize()}>Синхронізувати метадані ↗</button></div>
        </section>}
      </main>}
    </div>
    <footer className="site-footer"><p>Дані та зображення фільмів: <a href="https://www.themoviedb.org/" target="_blank" rel="noreferrer">TMDB</a>. Цей продукт використовує TMDB API, але не схвалений і не сертифікований TMDB.</p></footer>
    {token && mobileMore && <div id="mobile-more-menu" className="mobile-more-menu" role="menu" aria-label="Додаткова навігація">{nav.slice(4).map(([name, label, icon]) => <button role="menuitem" key={name} className={section === name ? 'nav-active' : ''} onClick={() => navigate(name)}><span>{icon}</span>{label}</button>)}{role === 'admin' && <button role="menuitem" className={section === 'admin' ? 'nav-active' : ''} onClick={() => navigate('admin')}><span>⚙</span>Адмін</button>}</div>}
    <nav className="mobile-nav" aria-label="Мобільна навігація">{nav.filter(([name]) => name === 'catalog' || (token && ['recommendations', 'favorites', 'watchlist'].includes(name))).map(([name, label, icon]) => <button key={name} className={section === name ? 'nav-active' : ''} onClick={() => navigate(name)}><span>{icon}</span>{label}</button>)}{token && <button aria-expanded={mobileMore} aria-controls="mobile-more-menu" className={mobileMore || ['watched', 'history', 'account', 'admin'].includes(section) ? 'nav-active' : ''} onClick={() => setMobileMore(value => !value)}><span>•••</span>Ще</button>}</nav>
  </div>;
}
