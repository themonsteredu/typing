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
순서대로 처리합니다.

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

## AI 제공자

기본은 **Anthropic Claude**입니다. 설정에서 단계별 모델을 지정할 수 있고, 키가 없으면
파이프라인은 결정적(deterministic) 폴백으로 동작해 전체 흐름을 확인할 수 있습니다.

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

## 라이선스 / 결과물

생성된 HWPX 문서에 대한 권리는 사용자에게 있으며 자유롭게 배포할 수 있습니다.

## 개발

```bash
cd studio && pnpm test       # Vitest
cd engine && python -m pytest    # 엔진 단위 테스트
```
