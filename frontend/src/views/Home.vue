<template>
  <div class="home-container">
    <a-card>
      <template #title>
        <h2>🎬 视频AI总结</h2>
      </template>
      
      <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
        <a-tab-pane key="single" tab="单个视频">
          <a-form @finish="handleSubmit" :model="formData" layout="vertical">
            <a-form-item label="视频链接" name="url" :rules="[{ required: true, message: '请输入视频链接' }]">
              <a-textarea
                v-model:value="formData.url"
                placeholder="请输入视频链接（支持抖音/TikTok/Bilibili）"
                :rows="4"
                size="large"
                :disabled="loading"
                @input="handleUrlInput"
                @blur="handleUrlBlur"
              />
              
              <!-- 链接识别结果 -->
              <div v-if="urlAnalysis" class="url-analysis">
                <a-alert
                  :message="urlAnalysis.platform_name"
                  :description="`类型: ${urlAnalysis.type_name}${urlAnalysis.video_id ? ' | ID: ' + urlAnalysis.video_id : ''}`"
                  :type="urlAnalysis.is_supported ? 'success' : 'warning'"
                  show-icon
                  :closable="false"
                  style="margin-top: 12px;"
                >
                  <template #icon>
                    <component :is="getPlatformIcon(urlAnalysis.platform)" />
                  </template>
                </a-alert>
                
                <div v-if="!urlAnalysis.is_supported" class="unsupported-tip">
                  <a-typography-text type="warning">
                    该平台暂不支持，请使用抖音、TikTok 或 Bilibili 链接
                  </a-typography-text>
                </div>
              </div>
              
              <!-- 识别中提示 -->
              <div v-if="analyzing" class="analyzing">
                <a-spin size="small" />
                <span style="margin-left: 8px; color: #999;">正在识别链接类型...</span>
              </div>
            </a-form-item>
            
            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="loading"
                :disabled="loading || (urlAnalysis && !urlAnalysis.is_supported)"
                block
              >
                <template #icon>
                  <component :is="h(PlayCircleOutlined)" />
                </template>
                开始处理
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="batch" tab="批量处理">
          <a-form @finish="handleBatchSubmit" :model="batchFormData" layout="vertical">
            <a-form-item label="链接类型" name="type">
              <a-select 
                v-model:value="batchFormData.type" 
                size="large" 
                :disabled="loading"
                @change="handleBatchTypeChange"
              >
                <a-select-option value="auto">自动识别</a-select-option>
                <a-select-option value="mix">合集/合辑</a-select-option>
                <a-select-option value="account">用户主页</a-select-option>
                <a-select-option value="video">视频链接</a-select-option>
              </a-select>
              <template #help>
                <span style="color: #999; font-size: 12px;">
                  自动识别：自动判断链接类型和平台<br/>
                  合集/合辑：分析合集内的所有视频<br/>
                  用户主页：分析用户的所有作品<br/>
                  视频链接：只处理单个视频
                </span>
              </template>
            </a-form-item>
            
            <a-form-item label="链接地址" name="url" :rules="[{ required: true, message: '请输入链接' }]">
              <a-textarea
                v-model:value="batchFormData.url"
                placeholder="请输入合集链接、作者主页链接或视频链接"
                :rows="3"
                size="large"
                :disabled="loading"
                @input="handleBatchUrlInput"
                @blur="handleBatchUrlBlur"
              />
              
              <!-- 批量链接识别结果 -->
              <div v-if="batchUrlAnalysis" class="url-analysis">
                <a-alert
                  :message="batchUrlAnalysis.platform_name"
                  :description="`类型: ${batchUrlAnalysis.type_name}${batchUrlAnalysis.video_id ? ' | ID: ' + batchUrlAnalysis.video_id : ''}`"
                  :type="batchUrlAnalysis.is_supported ? 'success' : 'warning'"
                  show-icon
                  :closable="false"
                  style="margin-top: 12px;"
                >
                  <template #icon>
                    <component :is="getPlatformIcon(batchUrlAnalysis.platform)" />
                  </template>
                </a-alert>
                
                <!-- 自动建议类型 -->
                <div v-if="batchUrlAnalysis && batchFormData.type === 'auto'" class="type-suggestion">
                  <a-typography-text type="secondary" style="font-size: 12px;">
                    已自动识别为: <strong>{{ batchUrlAnalysis.type_name }}</strong>
                  </a-typography-text>
                </div>
                
                <div v-if="!batchUrlAnalysis.is_supported" class="unsupported-tip">
                  <a-typography-text type="warning">
                    该平台暂不支持，请使用抖音、TikTok 或 Bilibili 链接
                  </a-typography-text>
                </div>
              </div>
              
              <!-- 识别中提示 -->
              <div v-if="analyzingBatch" class="analyzing">
                <a-spin size="small" />
                <span style="margin-left: 8px; color: #999;">正在识别链接类型...</span>
              </div>
            </a-form-item>
            
            <a-form-item label="最大数量" name="max_count">
              <a-input-number
                v-model:value="batchFormData.max_count"
                :min="1"
                :max="500"
                size="large"
                :disabled="loading"
                style="width: 100%"
              />
              <template #help>
                <span style="color: #999; font-size: 12px;">限制最多处理多少个视频，防止数量过多</span>
              </template>
            </a-form-item>
            
            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="loading"
                :disabled="loading || (batchUrlAnalysis && !batchUrlAnalysis.is_supported)"
                block
              >
                <template #icon>
                  <component :is="h(PlayCircleOutlined)" />
                </template>
                开始批量处理
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
      
      <a-result
        v-if="result"
        :status="result.success ? 'success' : 'error'"
        :title="result.success ? '任务已创建' : '创建失败'"
        :sub-title="result.message"
      >
        <template #extra>
          <a-button type="primary" @click="goToTasks">查看任务</a-button>
          <a-button @click="reset">继续处理</a-button>
        </template>
      </a-result>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'
import { 
  CheckCircleOutlined, 
  QuestionCircleOutlined,
  VideoCameraOutlined,
  YoutubeOutlined
} from '@ant-design/icons-vue'
import { processVideo, processBatchVideos, analyzeUrl, type UrlAnalysis } from '@/api/task'

const router = useRouter()

const loading = ref(false)
const activeTab = ref('single')
const analyzing = ref(false)
const analyzingBatch = ref(false)
const urlAnalysis = ref<UrlAnalysis | null>(null)
const batchUrlAnalysis = ref<UrlAnalysis | null>(null)

const STORAGE_KEY = 'tiktok-downloader-last-url'

const formData = reactive({
  url: '',
})

const batchFormData = reactive({
  url: '',
  type: 'auto',
  max_count: 100,
})

const result = ref<{
  success: boolean
  message: string
}>()

// 防抖定时器
let analyzeTimer: ReturnType<typeof setTimeout> | null = null
let analyzeBatchTimer: ReturnType<typeof setTimeout> | null = null

// 从 localStorage 加载最后的 URL
const loadLastUrl = () => {
  try {
    const lastUrl = localStorage.getItem(STORAGE_KEY)
    if (lastUrl) {
      formData.url = lastUrl
      // 自动分析已加载的 URL
      if (lastUrl.trim()) {
        analyzeUrlDebounced(lastUrl)
      }
    }
  } catch (error) {
    console.error('Failed to load from localStorage:', error)
  }
}

// 组件挂载时加载数据
onMounted(() => {
  loadLastUrl()
})

// 分析单个视频链接
const analyzeUrlDebounced = (url: string) => {
  if (analyzeTimer) {
    clearTimeout(analyzeTimer)
  }
  
  if (!url.trim()) {
    urlAnalysis.value = null
    return
  }
  
  analyzing.value = true
  analyzeTimer = setTimeout(async () => {
    try {
      const response = await analyzeUrl(url)
      if (response.success) {
        urlAnalysis.value = response.data
      }
    } catch (error: any) {
      console.error('Failed to analyze URL:', error)
      urlAnalysis.value = null
    } finally {
      analyzing.value = false
    }
  }, 500) // 500ms 防抖
}

// 分析批量链接
const analyzeBatchUrlDebounced = (url: string) => {
  if (analyzeBatchTimer) {
    clearTimeout(analyzeBatchTimer)
  }
  
  if (!url.trim()) {
    batchUrlAnalysis.value = null
    return
  }
  
  analyzingBatch.value = true
  analyzeBatchTimer = setTimeout(async () => {
    try {
      const response = await analyzeUrl(url)
      if (response.success) {
        batchUrlAnalysis.value = response.data
      }
    } catch (error: any) {
      console.error('Failed to analyze batch URL:', error)
      batchUrlAnalysis.value = null
    } finally {
      analyzingBatch.value = false
    }
  }, 500) // 500ms 防抖
}

// 单个视频链接输入处理
const handleUrlInput = () => {
  urlAnalysis.value = null
  analyzeUrlDebounced(formData.url)
}

const handleUrlBlur = () => {
  if (formData.url.trim()) {
    analyzeUrlDebounced(formData.url)
  }
}

// 批量链接输入处理
const handleBatchUrlInput = () => {
  batchUrlAnalysis.value = null
  analyzeBatchUrlDebounced(batchFormData.url)
}

const handleBatchUrlBlur = () => {
  if (batchFormData.url.trim()) {
    analyzeBatchUrlDebounced(batchFormData.url)
  }
}

// 批量类型变化处理
const handleBatchTypeChange = () => {
  if (batchFormData.type === 'auto' && batchFormData.url.trim()) {
    analyzeBatchUrlDebounced(batchFormData.url)
  }
}

// 获取平台图标
const getPlatformIcon = (platform: string) => {
  const iconMap: Record<string, any> = {
    'douyin': CheckCircleOutlined,
    'tiktok': YoutubeOutlined,
    'bilibili': VideoCameraOutlined,
    'unknown': QuestionCircleOutlined,
  }
  return iconMap[platform] || QuestionCircleOutlined
}

const handleSubmit = async (values: any) => {
  loading.value = true
  
  try {
    const response = await processVideo({
      url: values.url,
    })
    
    result.value = {
      success: response.success,
      message: response.message,
    }
    
    if (response.success) {
      // 保存处理成功的 URL 到 localStorage
      try {
        localStorage.setItem(STORAGE_KEY, values.url)
      } catch (error) {
        console.error('Failed to save to localStorage:', error)
      }
      
      message.success('任务创建成功，正在处理...')
      // 跳转到任务管理页面
      setTimeout(() => {
        router.push('/tasks')
      }, 2000)
    }
  } catch (error: any) {
    message.error(error.message || '处理失败')
    result.value = {
      success: false,
      message: error.message || '处理失败',
    }
  } finally {
    loading.value = false
  }
}

const handleBatchSubmit = async (values: any) => {
  loading.value = true
  
  try {
    message.info('正在提取视频链接，请稍候...')
    
    const response = await processBatchVideos({
      url: values.url,
      type: values.type,
      max_count: values.max_count || 100,
    })
    
    result.value = {
      success: response.success,
      message: response.message,
    }
    
    if (response.success) {
      const count = response.data?.created || 0
      message.success(`成功创建 ${count} 个任务，正在处理...`)
      // 跳转到任务管理页面
      setTimeout(() => {
        router.push('/tasks')
      }, 2000)
    }
  } catch (error: any) {
    message.error(error.message || '批量处理失败')
    result.value = {
      success: false,
      message: error.message || '批量处理失败',
    }
  } finally {
    loading.value = false
  }
}

const handleTabChange = (_key: string) => {
  result.value = undefined
  urlAnalysis.value = null
  batchUrlAnalysis.value = null
}

const goToTasks = () => {
  router.push('/tasks')
}

const reset = () => {
  result.value = undefined
}
</script>

<style scoped>
.home-container {
  max-width: 900px;
  margin: 0 auto;
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

h2 {
  margin: 0;
}

:deep(.ant-card) {
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.98);
  transition: all 0.3s ease;
}

:deep(.ant-card:hover) {
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.12);
  transform: translateY(-2px);
}

:deep(.ant-card-head) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 20px 24px;
}

:deep(.ant-card-body) {
  padding: 32px;
}

.url-analysis {
  margin-top: 8px;
}

.analyzing {
  display: flex;
  align-items: center;
  margin-top: 8px;
  padding: 8px 0;
}

.unsupported-tip {
  margin-top: 8px;
  padding: 8px;
  background: #fff7e6;
  border-radius: 4px;
}

.type-suggestion {
  margin-top: 8px;
  padding: 4px 8px;
  background: #f0f0f0;
  border-radius: 4px;
}
</style>
