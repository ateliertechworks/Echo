export default function Avatar({ user, size = 36 }) {
  const initials = (user?.username || user?.email || '?')
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join('');
  return (
    <div className="avatar" style={{ width: size, height: size, fontSize: size * 0.4 }}>
      {user?.profile_photo ? <img src={user.profile_photo} alt="" /> : initials}
    </div>
  );
}
