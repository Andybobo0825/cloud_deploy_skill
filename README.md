# cloud_deploy_skill

本專案提供一個 Codex Skill：`terraform-cloud-planner`，用來在建立或修改 Terraform / IaC 前，先完成應用程式架構偵測、雲端需求訪談、部署規格整理與驗證規劃，避免直接產生零散或不符合需求的基礎設施程式碼。

## Skill 概覽

- **名稱**：`terraform-cloud-planner`
- **用途**：引導式 Terraform / 雲端部署規劃 workflow
- **適用場景**：當需要建立、生成、 scaffold 或修改 Terraform 設定時使用
- **核心目標**：先理解應用程式技術棧與部署需求，再產出標準化 Terraform 實作計畫，最後才進行 infra 檔案編輯

## 解決的問題

一般直接要求 AI 產生 Terraform 時，容易出現以下問題：

- 未確認應用程式語言、框架、runtime port 或部署型態
- 未區分 demo、staging、production 等不同環境需求
- 沒有確認雲端區域、服務清單、成本限制、HA / security 條件
- demo 專案被過度設計成 production-grade 架構
- Terraform 檔案產生後缺少 intake 文件、假設記錄與驗證步驟

`terraform-cloud-planner` 透過「先偵測、再訪談、再規劃、後實作」的流程，降低這些風險。

## 工作流程

Skill 的強制流程如下：

1. **偵測目前專案技術棧**
   - 執行 `scripts/detect_stack.py <repo-root>`
   - 檢查語言、框架、package manager、runtime port
   - 檢查 Dockerfile、Compose、CI/CD、既有 Terraform / infra 檔案

2. **進行雲端部署需求訪談**
   - 在修改 Terraform 前，先確認必要需求
   - 針對 demo / portfolio 使用低成本預設
   - 針對 production 追問 HA、安全、備份、監控與擴展需求

3. **整理 Terraform implementation profile**
   - 產生或更新 `infra/terraform-intake.md`
   - 記錄偵測結果、假設、provider / region、服務清單、資源 sizing、安全與成本限制

4. **建立或修改 Terraform**
   - 保留既有應用程式語言與架構邊界
   - 優先使用小而可審查的 infra 變更
   - 不在未授權情況下使用 credentials 或 apply infrastructure

5. **驗證**
   - 執行 `terraform fmt -recursive`
   - 在 provider / init context 可用時執行 `terraform validate`
   - 若無法驗證，需記錄原因並執行次佳靜態檢查

## 必要訪談欄位

在編輯 Terraform 前，Skill 會收集或明確標記以下欄位為假設：

- Cloud provider 與 region，例如 AWS `ap-east-1`、`ap-northeast-1`、`us-east-1`
- 環境用途：demo、portfolio、staging、production 或 DR
- 預期流量與規模：使用者數、RPS、jobs、資料量、成長窗口
- Runtime model：VM、container、serverless、managed platform 或沿用既有選擇
- Compute sizing：
  - VM：instance type、OS、disk size
  - Container：CPU、memory、desired count、port、health check
  - Serverless：memory、timeout、concurrency
- 需要的服務：network、load balancer、DNS/TLS、registry、database、cache、queue、secrets、logging、monitoring、CI/CD
- 可用性：single-AZ / multi-AZ、autoscaling、rolling deployment、backup / restore
- 安全性：public/private subnet、ingress source、secrets handling、IAM boundary、encryption
- 成本限制與清除策略
- 命名與 tagging convention

## Demo 預設策略

當使用者選擇 demo 或 portfolio，且沒有額外要求時，Skill 會偏向：

- 使用最少、低成本且容易清除的 managed resources
- 避免 NAT Gateway、WAF、RDS Multi-AZ、private endpoints、Route 53 / TLS 等額外成本項目
- Container 專案優先考慮 Fargate 或小型 VM，而非 Kubernetes
- Desired count 預設為 `1`
- CloudWatch log retention 使用 7 至 14 天
- Container registry 啟用 ECR image scan on push

## Production Gate

如果使用者明確表示 production / prd，Skill 不會默默套用 demo defaults，而會進一步確認：

- Multi-AZ、private subnet、NAT / egress 策略
- Secrets Manager / Parameter Store 與加密需求
- Autoscaling 門檻與 rollback policy
- Backup retention、RPO / RTO
- Monitoring、alerts、access control
- 成本範圍與 compliance 限制

## 專案結構

```text
skill/terraform-cloud-planner/
├── SKILL.md                         # Skill 主要說明與工作流程
├── agents/openai.yaml               # OpenAI / Codex agent 顯示資訊與預設 prompt
├── scripts/detect_stack.py          # 專案技術棧與 infra hints 偵測工具
└── references/aws-question-bank.md  # AWS 訪談問題、demo defaults 與服務映射參考
```

## 使用方式

將 `skill/terraform-cloud-planner` 安裝或放入 Codex 可讀取的 skills 目錄後，可在需要規劃 Terraform 時要求 Codex 使用此 Skill，例如：

```text
使用 terraform-cloud-planner 幫我為這個專案規劃 AWS Terraform 部署。
```

或：

```text
請先偵測我的應用程式 stack，訪談部署需求，再產生 Terraform plan。
```

Skill 會先輸出類似以下摘要，確認偵測結果與實作 profile 後才開始編輯 Terraform：

```markdown
Mode: terraform-cloud-planner
Detected stack: ...
Terraform profile: demo|staging|production, region=..., runtime=..., scale=...
Resources to create/change: ...
Assumptions: ...
Proceeding to edit: infra/<files>
```

## 偵測工具

`detect_stack.py` 可獨立執行，用來取得專案技術棧與 infra hints：

```bash
python3 skill/terraform-cloud-planner/scripts/detect_stack.py <repo-root>
```

輸出內容包含：

- repo root
- 偵測到的 languages / frameworks / package managers
- Dockerfile、Compose、CI/CD、runtime port 等 hints
- 既有 Terraform providers、resource types 與 resource count
- root notable files

## 產出物

使用此 Skill 後，通常會產生或更新：

- `infra/terraform-intake.md`：部署需求、假設與 Terraform plan
- `infra/*.tf`：Terraform resources、variables、outputs、providers 等檔案
- 驗證紀錄：`terraform fmt`、`terraform validate` 或替代檢查結果

## 注意事項

- 此 Skill 只負責規劃與產生 Terraform，不會在未授權情況下 apply infrastructure。
- 不會使用 credentials，除非使用者明確要求且具備權限。
- Production 環境需要更完整的安全、HA、備份、監控與成本確認。
- Demo / portfolio 環境預設以低成本、易 teardown、少資源為原則。
