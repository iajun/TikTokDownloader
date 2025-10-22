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
                placeholder="请输入抖音/TikTok视频链接，支持长链接、短链接"
                :rows="4"
                size="large"
                :disabled="loading"
              />
            </a-form-item>
            
            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="loading"
                :disabled="loading"
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
              <a-select v-model:value="batchFormData.type" size="large" :disabled="loading">
                <a-select-option value="auto">自动识别</a-select-option>
                <a-select-option value="mix">抖音合集</a-select-option>
                <a-select-option value="account">作者作品</a-select-option>
                <a-select-option value="video">视频链接</a-select-option>
              </a-select>
              <template #help>
                <span style="color: #999; font-size: 12px;">
                  自动识别：自动判断链接类型<br/>
                  抖音合集：分析合集内的所有视频<br/>
                  作者作品：分析作者的所有作品<br/>
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
              />
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
                :disabled="loading"
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
import { processVideo, processBatchVideos } from '@/api/task'

const router = useRouter()

const loading = ref(false)
const activeTab = ref('single')

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

// 从 localStorage 加载最后的 URL
const loadLastUrl = () => {
  try {
    const lastUrl = localStorage.getItem(STORAGE_KEY)
    if (lastUrl) {
      formData.url = lastUrl
    }
  } catch (error) {
    console.error('Failed to load from localStorage:', error)
  }
}

// 组件挂载时加载数据
onMounted(() => {
  loadLastUrl()
})

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
</style>
