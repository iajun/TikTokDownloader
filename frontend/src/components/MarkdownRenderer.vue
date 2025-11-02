<template>
  <div v-if="content" class="markdown-content" ref="markdownContainer" v-html="renderedContent"></div>
  <div v-else class="markdown-content-empty">暂无内容</div>

  <!-- Mermaid 放大查看弹窗 -->
  <a-modal
    v-model:open="showMermaidModal"
    :footer="null"
    width="80%"
    :bodyStyle="{ padding: '0' }"
  >
    <div class="mermaid-modal">
      <div class="mermaid-modal-toolbar">
        <a-button size="small" @click="zoomOut">-</a-button>
        <span class="zoom-text">{{ Math.round(modalZoom * 100) }}%</span>
        <a-button size="small" @click="zoomIn">+</a-button>
        <a-button size="small" @click="resetZoom" style="margin-left: 8px">重置</a-button>
        <a-button size="small" @click="copyMermaidToClipboard" style="margin-left: 8px" type="primary">📋 复制图片</a-button>
      </div>
      <div class="mermaid-modal-body">
        <div class="mermaid-modal-canvas" :style="{ transform: `scale(${modalZoom})` }" ref="mermaidModalContainer" v-html="modalSvg"></div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import mermaid from 'mermaid'
import { message } from 'ant-design-vue'

interface Props {
  content: string
}

const props = defineProps<Props>()

const renderedContent = ref('')
const markdownContainer = ref<HTMLElement | null>(null)

// Modal state for zoom view
const showMermaidModal = ref(false)
const modalSvg = ref('')
const modalZoom = ref(1)
const mermaidModalContainer = ref<HTMLElement | null>(null)

const zoomIn = () => { modalZoom.value = Math.min(3, +(modalZoom.value + 0.1).toFixed(2)) }
const zoomOut = () => { modalZoom.value = Math.max(0.2, +(modalZoom.value - 0.1).toFixed(2)) }
const resetZoom = () => { modalZoom.value = 1 }

// 复制 Mermaid 图表到剪切板
const copyMermaidToClipboard = async () => {
  if (!mermaidModalContainer.value) return
  
  try {
    const svgElement = mermaidModalContainer.value.querySelector('svg')
    if (!svgElement) {
      console.error('No SVG element found')
      return
    }
    
    // 克隆 SVG 元素以避免修改原始元素
    const svgClone = svgElement.cloneNode(true) as SVGElement
    
    // 获取 SVG 的实际尺寸（优先使用 viewBox，否则使用 width/height 属性，最后使用 getBoundingClientRect）
    let width: number
    let height: number
    
    const viewBox = svgElement.getAttribute('viewBox')
    if (viewBox) {
      const parts = viewBox.split(/\s+/)
      if (parts.length >= 4) {
        width = parseFloat(parts[2]) || 800
        height = parseFloat(parts[3]) || 600
      } else {
        const bbox = svgElement.getBoundingClientRect()
        width = bbox.width || 800
        height = bbox.height || 600
      }
    } else {
      width = parseFloat(svgElement.getAttribute('width') || '0') || 
              svgElement.getBoundingClientRect().width || 800
      height = parseFloat(svgElement.getAttribute('height') || '0') || 
               svgElement.getBoundingClientRect().height || 600
    }
    
    // 确保尺寸合理（至少 100px）
    width = Math.max(width, 100)
    height = Math.max(height, 100)
    
    // 创建一个 canvas 元素
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    
    if (!ctx) {
      console.error('Failed to get canvas context')
      return
    }
    
    // 设置白色背景
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    
    // 将 SVG 转为 data URI（避免跨域污染问题）
    // 确保 SVG 有正确的 width 和 height 属性
    svgClone.setAttribute('width', width.toString())
    svgClone.setAttribute('height', height.toString())
    const svgWithSize = new XMLSerializer().serializeToString(svgClone)
    const svgDataUri = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgWithSize)
    
    const img = new Image()
    // 对于 data URI，不需要设置 crossOrigin
    
    await new Promise((resolve, reject) => {
      img.onload = () => {
        try {
          // 绘制图片到 canvas
          ctx.drawImage(img, 0, 0, width, height)
          
          // 将 canvas 转为 blob
          canvas.toBlob((blob) => {
            if (!blob) {
              reject(new Error('Failed to create blob'))
              return
            }
            
            // 使用 Clipboard API 复制图片
            navigator.clipboard.write([
              new ClipboardItem({
                'image/png': blob
              })
            ]).then(() => {
              message.success('图片已复制到剪切板')
              resolve(true)
            }).catch(reject)
          }, 'image/png')
        } catch (error) {
          reject(error)
        }
      }
      img.onerror = () => {
        reject(new Error('Failed to load SVG image'))
      }
      img.src = svgDataUri
    })
  } catch (error) {
    console.error('Failed to copy Mermaid chart:', error)
    message.error('复制失败：' + (error instanceof Error ? error.message : String(error)))
  }
}

// 复制 Mermaid 图表到剪切板（从容器元素复制）
const copyMermaidChartToClipboard = async (container: HTMLElement) => {
  try {
    const svgElement = container.querySelector('svg')
    if (!svgElement) {
      message.error('未找到图表')
      return
    }
    
    // 克隆 SVG 元素以避免修改原始元素
    const svgClone = svgElement.cloneNode(true) as SVGElement
    
    // 获取 SVG 的实际尺寸（优先使用 viewBox，否则使用 width/height 属性，最后使用 getBoundingClientRect）
    let width: number
    let height: number
    
    const viewBox = svgElement.getAttribute('viewBox')
    if (viewBox) {
      const parts = viewBox.split(/\s+/)
      if (parts.length >= 4) {
        width = parseFloat(parts[2]) || 800
        height = parseFloat(parts[3]) || 600
      } else {
        const bbox = svgElement.getBoundingClientRect()
        width = bbox.width || 800
        height = bbox.height || 600
      }
    } else {
      width = parseFloat(svgElement.getAttribute('width') || '0') || 
              svgElement.getBoundingClientRect().width || 800
      height = parseFloat(svgElement.getAttribute('height') || '0') || 
               svgElement.getBoundingClientRect().height || 600
    }
    
    // 确保尺寸合理（至少 100px）
    width = Math.max(width, 100)
    height = Math.max(height, 100)
    
    // 创建一个 canvas 元素
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    
    if (!ctx) {
      message.error('无法创建画布')
      return
    }
    
    // 设置白色背景
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    
    // 将 SVG 转为 data URI（避免跨域污染问题）
    // 确保 SVG 有正确的 width 和 height 属性
    svgClone.setAttribute('width', width.toString())
    svgClone.setAttribute('height', height.toString())
    const svgWithSize = new XMLSerializer().serializeToString(svgClone)
    const svgDataUri = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgWithSize)
    
    const img = new Image()
    // 对于 data URI，不需要设置 crossOrigin
    
    await new Promise((resolve, reject) => {
      img.onload = () => {
        try {
          // 绘制图片到 canvas
          ctx.drawImage(img, 0, 0, width, height)
          
          // 将 canvas 转为 blob
          canvas.toBlob((blob) => {
            if (!blob) {
              reject(new Error('Failed to create blob'))
              return
            }
            
            // 使用 Clipboard API 复制图片
            navigator.clipboard.write([
              new ClipboardItem({
                'image/png': blob
              })
            ]).then(() => {
              message.success('图片已复制到剪切板')
              resolve(true)
            }).catch(reject)
          }, 'image/png')
        } catch (error) {
          reject(error)
        }
      }
      img.onerror = () => {
        reject(new Error('Failed to load SVG image'))
      }
      img.src = svgDataUri
    })
  } catch (error) {
    console.error('Failed to copy Mermaid chart:', error)
    message.error('复制失败：' + (error instanceof Error ? error.message : String(error)))
  }
}

// 初始化 mermaid
onMounted(() => {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'loose',
    themeVariables: {
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
      primaryColor: '#f5f7ff',
      primaryTextColor: '#1f2937',
      primaryBorderColor: '#c7d2fe',
      lineColor: '#94a3b8',
      secondaryColor: '#eef2ff',
      tertiaryColor: '#ffffff',
      noteBkgColor: '#ecfeff',
      noteBorderColor: '#06b6d4',
      edgeLabelBackground: '#ffffff',
      clusterBkg: '#ffffff',
      clusterBorder: '#e5e7eb',
      nodeBorderRadius: 8,
      fontSize: '13px'
    },
  })
})

// 渲染 mermaid 图表
const renderMermaid = async () => {
  await nextTick()
  if (!markdownContainer.value) return
  
  const mermaidElements = markdownContainer.value.querySelectorAll('code.language-mermaid')
  
  for (const element of Array.from(mermaidElements)) {
    const code = element.textContent || ''
    const codeBlock = element.closest('pre')
    
    if (code.trim() && codeBlock) {
      const id = 'mermaid-' + Math.random().toString(36).substring(7)
      const container = document.createElement('div')
      container.className = 'mermaid-container'
      container.title = '点击放大查看，右键可复制图片'
      
      // 创建操作按钮容器
      const actionBar = document.createElement('div')
      actionBar.className = 'mermaid-action-bar'
      
      const copyBtn = document.createElement('button')
      copyBtn.className = 'mermaid-copy-btn'
      copyBtn.innerHTML = '📋 复制图片'
      copyBtn.title = '复制图片到剪切板'
      copyBtn.addEventListener('click', async (e) => {
        e.stopPropagation()
        await copyMermaidChartToClipboard(container)
      })
      
      const zoomBtn = document.createElement('button')
      zoomBtn.className = 'mermaid-zoom-btn'
      zoomBtn.innerHTML = '🔍 放大查看'
      zoomBtn.title = '点击放大查看'
      zoomBtn.addEventListener('click', () => {
        modalSvg.value = container.innerHTML
        showMermaidModal.value = true
        modalZoom.value = 1
      })
      
      actionBar.appendChild(copyBtn)
      actionBar.appendChild(zoomBtn)
      
      container.addEventListener('click', (e) => {
        // 如果点击的不是按钮，才触发放大
        if (!actionBar.contains(e.target as Node)) {
          modalSvg.value = container.innerHTML
          showMermaidModal.value = true
          modalZoom.value = 1
        }
      })
      
      try {
        // 使用 mermaid.render 方法渲染图表
        const result = await mermaid.render(id, code)
        // result 可能是一个包含 svg 属性的对象，或者直接是 svg 字符串
        const svgContent = typeof result === 'string' ? result : result.svg
        container.innerHTML = svgContent
        
        // 在 SVG 渲染后添加操作按钮
        container.appendChild(actionBar)
        
        // 替换原始代码块
        if (codeBlock.parentElement) {
          codeBlock.parentElement.replaceChild(container, codeBlock)
        }
      } catch (error) {
        console.error('Mermaid rendering error:', error)
        const errorDiv = document.createElement('div')
        errorDiv.className = 'mermaid-error'
        errorDiv.textContent = 'Mermaid 图表渲染失败: ' + (error instanceof Error ? error.message : String(error))
        errorDiv.style.cssText = 'padding: 16px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; color: #856404;'
        if (codeBlock.parentElement) {
          codeBlock.parentElement.replaceChild(errorDiv, codeBlock)
        }
      }
    }
  }
}

// 异步处理 Markdown 渲染
watch(() => props.content, async (newContent) => {
  if (!newContent) {
    renderedContent.value = ''
    return
  }
  
  try {
    // 使用 marked 将 Markdown 转换为 HTML
    const html = await marked(newContent)
    
    // 使用 DOMPurify 清理 HTML 以确保安全
    renderedContent.value = DOMPurify.sanitize(html, {
      ADD_TAGS: ['svg', 'g', 'path', 'circle', 'rect', 'line', 'text', 'foreignObject', 'polygon', 'polyline', 'ellipse', 'use', 'defs', 'title', 'marker', 'style', 'desc', 'tspan', 'textPath'],
      ADD_ATTR: ['viewBox', 'xmlns', 'xmlns:xlink', 'width', 'height', 'fill', 'stroke', 'stroke-width', 'stroke-miterlimit', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'd', 'points', 'transform', 'opacity', 'fill-opacity', 'stroke-opacity', 'font-size', 'font-family', 'font-weight', 'font-style', 'text-anchor', 'dominant-baseline', 'alignment-baseline', 'dy', 'dx', 'rotate', 'id', 'class', 'marker-start', 'marker-end', 'marker-mid', 'href', 'clip-path'],
    })
    
    // 等待 DOM 更新后渲染 mermaid 图表
    await nextTick()
    await renderMermaid()
  } catch (error) {
    console.error('Markdown rendering error:', error)
    renderedContent.value = newContent
  }
}, { immediate: true })
</script>

<style scoped>
.markdown-content {
  padding: 16px;
  line-height: 1.8;
  color: #333;
}

.markdown-content-empty {
  padding: 32px;
  text-align: center;
  color: #999;
}

/* Markdown 标题样式 */
.markdown-content :deep(h1) {
  font-size: 28px;
  font-weight: 600;
  margin: 24px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
  color: #1a1a1a;
}

.markdown-content :deep(h2) {
  font-size: 22px;
  font-weight: 600;
  margin: 20px 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
  color: #262626;
}

.markdown-content :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0 10px 0;
  color: #434343;
}

.markdown-content :deep(h4) {
  font-size: 16px;
  font-weight: 600;
  margin: 14px 0 8px 0;
  color: #595959;
}

/* 段落样式 */
.markdown-content :deep(p) {
  margin: 12px 0;
  line-height: 1.8;
}

/* 列表样式 */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 12px 0;
  padding-left: 24px;
}

.markdown-content :deep(ul) {
  list-style-type: disc;
  list-style-position: outside;
}

.markdown-content :deep(ol) {
  list-style-type: decimal;
  list-style-position: outside;
}

.markdown-content :deep(li) {
  margin: 8px 0;
  line-height: 1.7;
  padding-left: 0;
}

/* 代码块样式 */
.markdown-content :deep(pre) {
  background: #f7f7f7;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 16px;
  overflow-x: auto;
  margin: 16px 0;
  font-size: 14px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.markdown-content :deep(code) {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  color: #e83e8c;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  color: #333;
}

/* 引用样式 */
.markdown-content :deep(blockquote) {
  border-left: 4px solid #1890ff;
  padding: 12px 16px;
  margin: 16px 0;
  background: #f0f7ff;
  color: #595959;
  font-style: italic;
}

/* 分割线 */
.markdown-content :deep(hr) {
  border: none;
  border-top: 2px solid #f0f0f0;
  margin: 24px 0;
}

/* 表格样式 */
.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 12px;
  border: 1px solid #e0e0e0;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #fafafa;
  font-weight: 600;
}

.markdown-content :deep(tr:nth-child(even)) {
  background: #fafafa;
}

/* 链接样式 */
.markdown-content :deep(a) {
  color: #1890ff;
  text-decoration: none;
  transition: color 0.2s;
}

.markdown-content :deep(a:hover) {
  color: #40a9ff;
  text-decoration: underline;
}

/* 粗体和斜体 */
.markdown-content :deep(strong) {
  font-weight: 600;
  color: #1a1a1a;
}

.markdown-content :deep(em) {
  font-style: italic;
  color: #595959;
}

/* 删除线 */
.markdown-content :deep(del) {
  text-decoration: line-through;
  color: #999;
}

/* 图片样式 */
.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 第一行缩进 */
.markdown-content > *:first-child {
  margin-top: 0;
}

.markdown-content > *:last-child {
  margin-bottom: 0;
}

/* Mermaid 图表容器样式（现代化 + 最大高度） */
.markdown-content :deep(.mermaid-container) {
  margin: 24px auto;
  display: block;
  max-width: 100%;
  max-height: 600px;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 6px 18px rgba(31, 41, 55, 0.06);
  padding: 20px;
  overflow: auto;
  cursor: zoom-in;
  position: relative;
}

/* Mermaid 操作按钮栏 */
.markdown-content :deep(.mermaid-action-bar) {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 6px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  padding: 4px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.markdown-content :deep(.mermaid-copy-btn),
.markdown-content :deep(.mermaid-zoom-btn) {
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.markdown-content :deep(.mermaid-copy-btn:hover),
.markdown-content :deep(.mermaid-zoom-btn:hover) {
  background: #f0f0f0;
  border-color: #1890ff;
  color: #1890ff;
}

.markdown-content :deep(.mermaid-copy-btn:active),
.markdown-content :deep(.mermaid-zoom-btn:active) {
  background: #e6f7ff;
}

.markdown-content :deep(.mermaid-container svg) {
  width: 100% !important;
  height: auto !important;
  display: block;
}

/* 放大查看弹窗样式 */
.mermaid-modal {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.mermaid-modal-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
}

.zoom-text {
  min-width: 48px;
  text-align: center;
  color: #555;
}

.mermaid-modal-body {
  flex: 1;
  overflow: auto;
  background: #fafafa;
}

.mermaid-modal-canvas {
  transform-origin: top left;
  padding: 16px;
}

/* 小屏优化 */
@media (max-width: 768px) {
  .markdown-content :deep(.mermaid-container) {
    padding: 12px;
    border-radius: 10px;
  }

  .mermaid-modal {
    height: 70vh;
  }
}
</style>

