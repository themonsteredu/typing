# Exam Studio

수학 시험지 PDF를 AI로 분석해 **문제 추출 → 풀이 생성 → 도형 처리 → HWPX 문서 조립**까지
자동화하는 워크플로 도구입니다. (HWPX = 한컴오피스 한글의 개방형 문서 포맷, 사실상 ZIP + XML)

> 이 저장소는 동작하는 MVP 스캐폴드입니다. 4단계 파이프라인 전체가 연결되어 있으며,
> AI는 설정 패널에서 API 키를 저장한 뒤 사용합니다.

## 구조

```
typing/
├── studio/            # Next.js + TypeScript 웹 UI / 서버 (localhost:3020)
│   ├── app/           #   - 메인 파이프라인 화면, 설정 패널
│   │   └── api/       #   - 업로드/추출/생성/조립/설정 API 라우트
│   └── lib/           #   - 설정 저장, Python 엔진 호출 브리지
├── engine/            # Python 문서 엔진
│   └── exam_engine/   #   - PDF 파싱, AI 클라이언트, HWPX 생성, 파이프라인
├── bootstrap.ps1      # Windows 원라인 부트스트랩 (git clone/update 후 install 실행)
├── install.ps1        # Windows 의존성 설치 (Node/Python/AI CLI)
└── start.sh           # macOS/Linux 실행 런처
```

## 빠른 시작

### Windows (원라인 부트스트랩)

```powershell
irm https://raw.githubusercontent.com/themonsteredu/typing/main/bootstrap.ps1 | iex
```

부트스트랩이 Git → 저장소 클론 → `install.ps1`(Node 22+, Python 3.10+, 의존성 설치)을
순서대로 처리합니다. 설치가 끝나면 클론 폴더(`%USERPROFILE%\exam-studio`)의
**`run-dev.bat`을 더블클릭**하면 개발 서버가 뜨고 브라우저가 자동으로 열립니다.

> `run-dev.bat`/`run-dev.ps1`은 **소유자 본인 테스트용**으로 라이선스 잠금을
> 해제(`EXAM_STUDIO_DEV=1`)합니다. 고객에게 주는 배포본에서는 쓰지 말고,
> 고객은 아래 *라이선스 키* 절차로 활성화해서 사용합니다.

### macOS / Linux

```bash
git clone https://github.com/themonsteredu/typing.git
cd typing
./start.sh          # 의존성 설치 + 개발 서버 기동
```

이후 브라우저에서 <http://localhost:3020> 접속.

## 수동 설치

```bash
# 1) 웹 스튜디오
cd studio
pnpm install        # 또는 npm install
pnpm dev            # localhost:3020

# 2) Python 엔진
cd ../engine
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 사용 흐름

1. **설정**(`/settings`)에서 Anthropic API 키를 입력하고 저장합니다.
   키는 프로젝트 밖 `~/.exam-studio/settings.json`(0600 권한)에 로컬 저장됩니다.
   - **크롭 모드**(선택): 설정에서 *"크롭 모드 (문제를 원본 그대로 이미지로 삽입)"*를 켜면,
     재조판 대신 각 문제 영역을 페이지에서 그대로 잘라 이미지로 넣어 수식·그래프·도형이
     **원본 그대로** 보존됩니다. (API 키 필요, 켜면 비전 읽기보다 우선)
2. 메인 화면에서 시험지 **PDF를 업로드**합니다.
3. **파이프라인 실행** → 추출 / 풀이 생성 / 도형 처리 / HWPX 조립 단계가 순차로 진행되고
   로그가 실시간(SSE)으로 표시됩니다.
4. 완성된 **HWPX 파일을 다운로드**합니다.

## CLI (엔진 단독 사용)

```bash
cd engine
python -m exam_engine.cli extract  exam.pdf   --out work/
python -m exam_engine.cli generate work/      --out work/
python -m exam_engine.cli build    work/      --out output/exam.hwpx
# 또는 전체 파이프라인 한 번에
python -m exam_engine.cli run      exam.pdf   --out output/exam.hwpx
```

## AI 제공자 & 비전 추출

기본은 **Anthropic Claude**입니다. 설정에서 단계별 모델을 지정할 수 있고, 키가 없으면
파이프라인은 결정적(deterministic) 폴백으로 동작해 전체 흐름을 확인할 수 있습니다.

**AI 비전 추출(권장)**: 설정에서 켜면 각 페이지를 이미지로 만들어 Claude가 **수식까지 읽어**
문제를 구조화합니다. PDF의 수식은 특수 폰트라 일반 텍스트 추출 시 깨지는데, 비전 방식은 이를
해결합니다. (키 필요. 끄면 빠른 텍스트 추출로 폴백)

**지출/사용량**: 모든 AI 호출의 토큰 사용량과 예상 비용을 `~/.exam-studio/usage.json`에 집계하고
웹의 **지출**(`/usage`) 화면에서 보여줍니다. 단가표는 `engine/exam_engine/usage.py`(모델별 $/1M)에
있습니다. API 키는 설정 화면에서 언제든 변경·삭제할 수 있습니다.

```bash
# CLI에서도 확인 가능
python -m exam_engine.cli usage          # 누적 비용/토큰
python -m exam_engine.cli settings set --use-vision off   # 비전 끄기
python -m exam_engine.cli settings set --clear-key        # 키 삭제
```

## 도형(그림) 자동 검출

추출 단계에서 PDF 페이지에 포함된 이미지를 자동으로 검출하고, 페이지 내 위치를 기준으로
각 문제에 연결합니다(`Problem.figures`). 검출된 그림은:

- `work/figures/`에 잘려 저장되고,
- HWPX의 `BinData/imageN.<ext>`로 **임베드**되어 `header.xml`의 `binDataList`,
  `content.hpf` 매니페스트, `META-INF/manifest.xml`에 등록되며,
- 함께 생성되는 `preview.html`에 **인라인으로 렌더링**되어 바로 확인할 수 있습니다.

## HWPX 충실도(호환성)

`header.xml`은 글꼴(7개 언어 슬롯), 테두리/채우기(`borderFills`), 글자/문단 속성,
탭/번호/글머리표 목록 등 OWPML 참조 목록을 갖추도록 작성했습니다. 다만 특정 한컴오피스
빌드에서의 완벽한 호환은 실제 한글에서의 추가 검증이 필요합니다 — 이를 위해 항상 정확한
`preview.html`을 함께 출력합니다. (그림의 본문 내 인라인 *배치*는 문서가 안전하게 열리도록
현재 본문에는 자리표시자 문단으로 표시하고, 바이너리는 `BinData`로 임베드합니다.)

## 배포 (Docker)

Python 런타임과 장시간 실행 프로세스가 필요해 **서버리스(Vercel 등)에는 올라가지 않습니다.**
Node + Python을 한 컨테이너에 담아 배포합니다.

```bash
docker compose up --build      # http://localhost:3020
```

- 설정/라이선스/작업 파일은 `exam-studio-data` 볼륨(`/data`)에 보존됩니다.
- 개발 중 라이선스 게이트를 우회하려면 `EXAM_STUDIO_DEV=1`.
- 프로덕션 빌드는 Next.js standalone 출력(`next build`, `output: "standalone"`)을 사용합니다.

## 라이선스 키 (배포형 판매)

위조 불가능한 **Ed25519 서명 토큰**으로, 라이선스 서버 없이 **오프라인 검증**됩니다.
같은 토큰을 웹(Node)과 엔진(Python)이 동일하게 검증합니다.

**판매자(최초 1회 키 발급):**

```bash
cd engine
# 1) 서명용 키쌍 생성 — 개인키는 절대 외부 유출/커밋 금지
python tools/license_keygen.py genkeys --out tools/
#    출력된 공개키 PEM을 exam_engine/license.py 와 studio/lib/license.ts 의
#    DEFAULT_PUBLIC_KEY_PEM 에 넣거나, 환경변수 EXAM_STUDIO_LICENSE_PUBKEY 로 지정.

# 2) 구매자에게 줄 라이선스 키 발급 (예: 1년)
python tools/license_keygen.py issue --key tools/license_private_key.pem \
    --sub "buyer@example.com" --plan pro --days 365   # --days 0 = 무기한
```

**구매자(활성화):** 웹의 **라이선스** 화면(`/activate`)에 받은 키를 붙여넣고 활성화.
키는 사용자 컴퓨터 `~/.exam-studio/license.json`(0600)에만 저장되며 외부 전송되지 않습니다.
미활성 상태에서는 업로드/실행 API가 403으로 차단됩니다.

> 보안 메모: `engine/tools/license_private_key.pem`(개인키)은 `.gitignore`로 커밋이
> 차단되어 있습니다. 이 키가 유출되면 누구나 라이선스를 위조할 수 있으니 안전하게 보관하세요.

## 라이선스 / 결과물

생성된 HWPX 문서에 대한 권리는 사용자에게 있으며 자유롭게 배포할 수 있습니다.

## 개발

```bash
cd studio && pnpm test       # Vitest
cd engine && python -m pytest    # 엔진 단위 테스트
```
