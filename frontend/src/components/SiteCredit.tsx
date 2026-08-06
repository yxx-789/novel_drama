// 站点署名：让使用该网站的人知道它由谁制作
// 纯静态展示，不依赖任何后端数据
function SiteCredit() {
  return (
    <p className="mt-8 text-[11px] font-bold text-slate-400 tracking-[0.25em] uppercase">
      Made with <span className="text-rose-400">♥</span> by{' '}
      <span className="text-slate-600 font-semibold">xingyao</span>
    </p>
  )
}

export default SiteCredit
