import { useEffect, useState } from 'react'
import { fetchConfig, lockConfig, saveConfigKeys, unlockConfig, type ConfigInfo } from './api'

const KEY_FIELDS: { name: string; label: string; placeholder: string }[] = [
  { name: 'OPENAI_API_KEY', label: 'OpenAI API key', placeholder: 'sk-…' },
  { name: 'OPENROUTER_API_KEY', label: 'OpenRouter API key', placeholder: 'sk-or-…' },
  { name: 'ANTHROPIC_API_KEY', label: 'Anthropic API key', placeholder: 'sk-ant-…' },
  { name: 'OMNIROUTE_API_KEY', label: 'OmniRoute API key', placeholder: 'omni-…' },
  { name: 'EMBED_API_KEY', label: 'Embed API key', placeholder: 'sk-…' },
  { name: 'GITHUB_TOKEN', label: 'GitHub token', placeholder: 'ghp_…' },
]

export default function SettingsView() {
  const [config, setConfig] = useState<ConfigInfo | null>(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [keys, setKeys] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  const reload = () =>
    fetchConfig()
      .then(setConfig)
      .catch((err: Error) => setError(err.message))

  useEffect(() => {
    reload()
  }, [])

  const run = async (fn: () => Promise<{ status: string }>, okMsg: string) => {
    setBusy(true)
    setError('')
    setStatus('')
    try {
      const res = await fn()
      setStatus(`${okMsg} — server says: ${res.status}`)
      setPassphrase('')
      setKeys({})
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const save = () => run(() => saveConfigKeys(passphrase, keys), 'Keys encrypted to disk')
  const unlock = () => run(() => unlockConfig(passphrase), 'Keys unlocked for this session')
  const doLock = () => run(() => lockConfig(), 'Keys locked')

  if (error && !config) {
    return <p className="error">{error}</p>
  }
  if (!config) {
    return <p className="muted">loading…</p>
  }

  const canUnlock = passphrase.trim().length > 0 && !busy
  const canSave = canUnlock

  return (
    <div className="panel">
      <h2>Settings</h2>
      <table className="kv">
        <tbody>
          <tr>
            <td>LLM provider</td>
            <td>{config.provider}</td>
          </tr>
          <tr>
            <td>Embed model</td>
            <td>{config.embed_model ?? '(default)'}</td>
          </tr>
          <tr>
            <td>API key</td>
            <td>{config.api_key}</td>
          </tr>
          <tr>
            <td>GitHub token</td>
            <td>{config.github_token}</td>
          </tr>
          <tr>
            <td>Key store</td>
            <td>{config.encrypted ? 'encrypted on disk' : 'not created yet'}</td>
          </tr>
        </tbody>
      </table>

      <h3>Encrypted key store</h3>
      <p className="muted">
        Your passphrase encrypts the keys when they are saved to disk — it is never stored, so
        losing it makes the stored keys unrecoverable. Empty fields are skipped when saving.
      </p>
      <p className="muted">
        Save = write keys to disk, Unlock = make them available for this session, Lock = forget
        them in memory.
      </p>
      <label className="field">
        <span>Passphrase</span>
        <input
          type="password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
          placeholder="used to encrypt/decrypt the key store"
          autoComplete="new-password"
        />
      </label>
      {KEY_FIELDS.map((field) => (
        <label className="field" key={field.name}>
          <span>{field.label}</span>
          <input
            type="password"
            value={keys[field.name] ?? ''}
            onChange={(e) => setKeys({ ...keys, [field.name]: e.target.value })}
            placeholder={field.placeholder}
            autoComplete="new-password"
          />
        </label>
      ))}
      <div className="actions">
        <button onClick={save} disabled={!canSave}>
          Save keys (encrypt)
        </button>
        <button onClick={unlock} disabled={!canUnlock}>
          Unlock
        </button>
        <button onClick={doLock} disabled={busy}>
          Lock
        </button>
      </div>
      {busy && <p className="muted">working…</p>}
      {status && <p className="ok">{status}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
