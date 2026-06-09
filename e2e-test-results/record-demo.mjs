/**
 * macOS 屏幕录屏 + agent-browser walkthrough
 * 使用 @ffmpeg-installer/ffmpeg（仅安装在 e2e-test-results，不污染全局）
 */
import { spawn, execSync } from "node:child_process"
import { createRequire } from "node:module"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.join(__dirname, "demo", "demo-recording.mp4")

async function installFfmpeg() {
  try {
    const require = createRequire(import.meta.url)
    return require("@ffmpeg-installer/ffmpeg").path
  } catch {
    console.log("安装 @ffmpeg-installer/ffmpeg …")
    execSync("npm install @ffmpeg-installer/ffmpeg --no-save", {
      cwd: __dirname,
      stdio: "inherit",
    })
    const require = createRequire(import.meta.url)
    return require("@ffmpeg-installer/ffmpeg").path
  }
}

function listAvfoundationDevices(ffmpegPath) {
  try {
    const out = execSync(`${ffmpegPath} -f avfoundation -list_devices true -i "" 2>&1`, {
      encoding: "utf8",
    })
    return out
  } catch (err) {
    return err.stdout?.toString() || err.stderr?.toString() || ""
  }
}

function pickScreenDevice(devicesOutput) {
  const m = devicesOutput.match(/\[AVFoundation indev @[^\]]+\] AVFoundation video devices:\n([\s\S]*?)(?:\n\[|$)/)
  if (!m) return "1"
  const lines = m[1].trim().split("\n")
  const capture = lines.find((l) => /Capture screen|Screen/i.test(l))
  if (capture) {
    const idx = capture.match(/\[(\d+)\]/)?.[1]
    if (idx) return idx
  }
  return lines[0]?.match(/\[(\d+)\]/)?.[1] || "1"
}

async function main() {
  const ffmpegPath = await installFfmpeg()
  const devices = listAvfoundationDevices(ffmpegPath)
  const screenDev = pickScreenDevice(devices)
  console.log(`录屏设备: AVFoundation video [${screenDev}]`)

  const ff = spawn(
    ffmpegPath,
    [
      "-y",
      "-f",
      "avfoundation",
      "-framerate",
      "30",
      "-capture_cursor",
      "1",
      "-i",
      `${screenDev}:none`,
      "-c:v",
      "libx264",
      "-preset",
      "ultrafast",
      "-pix_fmt",
      "yuv420p",
      OUT,
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  )

  let ffLog = ""
  ff.stderr.on("data", (d) => {
    ffLog += d.toString()
  })

  await new Promise((r) => setTimeout(r, 2000))

  console.log("开始 agent-browser walkthrough …")
  const walk = spawn("node", ["agent-browser-walkthrough.mjs"], {
    cwd: __dirname,
    stdio: "inherit",
    env: { ...process.env, AGENT_BROWSER_HEADED: "1" },
  })

  const code = await new Promise((resolve) => walk.on("close", resolve))
  await new Promise((r) => setTimeout(r, 2000))

  ff.kill("SIGINT")
  await new Promise((resolve) => ff.on("close", resolve))

  if (code !== 0) {
    console.error("Walkthrough 退出码:", code)
    process.exit(code)
  }

  console.log("\n✓ 录屏已保存:", OUT)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
