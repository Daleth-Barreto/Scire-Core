import { useEffect, useState } from 'react'
import { fetchConfig, type ConfigInfo } from './api'

export default function SettingsView() {
  const [config, setConfig] = useState<ConfigInfo | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch((err: Error) => setError(err.message))
  }, [])

  if (error) {
    return <p className="error">{error}</p>
  }
  if (!config) {
    return <p className="muted">loading…</p>
  }

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
        </tbody>
      </table>
      <p className="muted">
        Keys are stored in your local .env file. Full values are never shown or sent to this
        frontend. Manage them with <code>scire config set &lt;key&gt; &lt;value&gt;</code>.
      </p>
    </div>
  )
}
