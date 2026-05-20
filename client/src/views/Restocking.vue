<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>
        <div class="budget-body">
          <div class="budget-display">
            {{ currencySymbol }}{{ budget.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
          </div>
          <input
            type="range"
            class="budget-slider"
            min="0"
            max="500000"
            step="1000"
            v-model.number="budget"
          />
          <div class="budget-bar-container">
            <div class="budget-bar">
              <div
                class="budget-bar-fill"
                :style="{ width: Math.min(budget > 0 ? (budgetUsed / budget) * 100 : 0, 100) + '%' }"
              ></div>
            </div>
            <div class="budget-bar-labels">
              <span>{{ t('restocking.budgetUsed') }}: {{ currencySymbol }}{{ budgetUsed.toLocaleString() }}</span>
              <span>{{ t('restocking.budgetRemaining') }}: {{ currencySymbol }}{{ budgetRemaining.toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recommendations Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            {{ t('restocking.recommendations') }}
            <span class="badge info count-badge">{{ recommendations.length }}</span>
          </h3>
        </div>

        <div v-if="budget === 0 || recommendations.length === 0" class="no-recommendations">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table class="recommendations-table">
            <thead>
              <tr>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="col-right">{{ t('restocking.table.restockQty') }}</th>
                <th class="col-right">{{ t('restocking.table.unitCost') }}</th>
                <th class="col-right">{{ t('restocking.table.lineTotal') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations" :key="item.sku">
                <td>{{ item.name }}</td>
                <td class="sku-cell">{{ item.sku }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td class="col-right">{{ item.quantity.toLocaleString() }}</td>
                <td class="col-right">{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td class="col-right line-total">
                  <strong>{{ currencySymbol }}{{ item.line_total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="total-row">
                <td colspan="5" class="total-label">{{ t('restocking.totalCost') }}</td>
                <td class="col-right total-value">
                  <strong>{{ currencySymbol }}{{ budgetUsed.toLocaleString() }}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Place Order Button -->
      <div v-if="recommendations.length > 0 && !orderSubmitted" class="order-action">
        <button
          class="btn-place-order"
          :disabled="submitting"
          @click="placeOrder"
        >
          {{ submitting ? t('common.loading') : t('restocking.placeOrder') }}
        </button>
      </div>

      <!-- Success Banner -->
      <div v-if="orderSubmitted" class="success-banner">
        <div class="success-content">
          <div class="success-message">{{ t('restocking.orderPlaced') }}</div>
          <div class="success-details">
            <span><strong>{{ t('restocking.orderId') }}:</strong> {{ submittedOrder.id }}</span>
            <span><strong>{{ t('restocking.expectedDelivery') }}:</strong> {{ formatDate(submittedOrder.expected_delivery) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale } = useI18n()
    const { } = useFilters()

    const forecasts = ref([])
    const loading = ref(false)
    const error = ref(null)
    const budget = ref(50000)
    const submitting = ref(false)
    const orderSubmitted = ref(false)
    const submittedOrder = ref(null)

    const currencySymbol = computed(() => currentCurrency.value === 'JPY' ? '¥' : '$')

    const formatDate = (dateString) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    const trendPriority = { increasing: 0, stable: 1, decreasing: 2 }

    const recommendations = computed(() => {
      if (budget.value === 0) return []

      const sorted = [...forecasts.value].sort((a, b) => {
        return (trendPriority[a.trend] ?? 1) - (trendPriority[b.trend] ?? 1)
      })

      let remaining = budget.value
      const result = []

      for (const forecast of sorted) {
        const restock_qty = Math.max(0, forecast.forecasted_demand - forecast.current_demand)
        if (restock_qty === 0) continue

        const cost = restock_qty * forecast.unit_cost
        if (cost <= remaining) {
          result.push({
            sku: forecast.item_sku,
            name: forecast.item_name,
            quantity: restock_qty,
            unit_cost: forecast.unit_cost,
            line_total: cost,
            trend: forecast.trend
          })
          remaining -= cost
        }
      }

      return result
    })

    const budgetUsed = computed(() => {
      return recommendations.value.reduce((sum, item) => sum + item.line_total, 0)
    })

    const budgetRemaining = computed(() => {
      return Math.max(0, budget.value - budgetUsed.value)
    })

    const loadForecasts = async () => {
      loading.value = true
      error.value = null
      try {
        forecasts.value = await api.getDemandForecasts()
      } catch (err) {
        error.value = t('common.error')
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      submitting.value = true
      try {
        const orderData = {
          budget: budget.value,
          items: recommendations.value.map(item => ({
            sku: item.sku,
            name: item.name,
            quantity: item.quantity,
            unit_cost: item.unit_cost,
            line_total: item.line_total
          }))
        }
        const result = await api.createRestockingOrder(orderData)
        submittedOrder.value = result
        orderSubmitted.value = true
      } catch (err) {
        error.value = t('common.error')
        console.error(err)
      } finally {
        submitting.value = false
      }
    }

    onMounted(() => loadForecasts())

    return {
      t,
      loading,
      error,
      budget,
      forecasts,
      recommendations,
      budgetUsed,
      budgetRemaining,
      currencySymbol,
      submitting,
      orderSubmitted,
      submittedOrder,
      placeOrder,
      formatDate
    }
  }
}
</script>

<style scoped>
.restocking {
  padding: 0;
}

.budget-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.budget-display {
  font-size: 2.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  height: 6px;
  accent-color: #2563eb;
  cursor: pointer;
}

.budget-bar-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.budget-bar {
  width: 100%;
  height: 10px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.budget-bar-fill {
  height: 100%;
  background: #2563eb;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.budget-bar-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  color: #64748b;
}

.count-badge {
  margin-left: 0.5rem;
  vertical-align: middle;
  font-size: 0.75rem;
}

.no-recommendations {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.recommendations-table {
  width: 100%;
  table-layout: auto;
}

.sku-cell {
  font-family: monospace;
  font-size: 0.813rem;
  color: #64748b;
}

.col-right {
  text-align: right;
}

.line-total {
  color: #0f172a;
}

.total-row {
  background: #f8fafc;
  border-top: 2px solid #e2e8f0;
}

.total-label {
  text-align: right;
  font-weight: 600;
  font-size: 0.875rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.75rem;
}

.total-value {
  font-size: 1rem;
  padding: 0.75rem;
  color: #0f172a;
}

.order-action {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 1.25rem;
}

.btn-place-order {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 2rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-place-order:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-place-order:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.success-banner {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}

.success-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.success-message {
  font-weight: 600;
  color: #065f46;
  font-size: 1rem;
}

.success-details {
  display: flex;
  gap: 2rem;
  font-size: 0.875rem;
  color: #047857;
}
</style>
