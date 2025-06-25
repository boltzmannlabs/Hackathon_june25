from langchain.tools import tool
from langchain_aws import ChatBedrock
import boto3 
from dotenv import load_dotenv
import os
load_dotenv()

client = boto3.client('bedrock-runtime', region_name="us-east-1", aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
sonnet_3_5 = ChatBedrock(
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    model_kwargs=dict(temperature=0),
    client=client
)
sonnet_3_7 = ChatBedrock(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    model_kwargs=dict(temperature=0),
    client=client
)

@tool("netlist_generator", return_direct=True)
def netlist_generator(input: str) -> str:
    """
    Generates a SPICE-format analog circuit netlist based on the user's design input.

    Args:
        input (str): User-provided circuit specification, including stage configuration,
                     topology, signals, and component types.

    Returns:
        str: Generated netlist as a string.
    """
    
    prompt = """ 
    You are a professional analog designer, and now you need to design the
    required analog circuits with the given design library of some analog basic
    components. Here is the library details, including CellNAME, PinINFO
    and detailDescription:
    [SubcirtuitLibrary]

    1. CellName:CascodeStageN
    PININFO:DRAIN(I/I)SOURCE(I/O)VBIAS(B)GND(P)
    Description:SingleNMOSCascode
    ************************************************************************
    *Library Name: DATASET *Cell Name: CascodeStageN *View Name: schematic
    ************************************************************************
    .SUBCKT CascodeStageN DRAIN SOURCE VBIAS GND
    *.PININFO DRAIN:B GND:B SOURCE:B VBIAS:B
    MM0 DRAIN VBIAS SOURCE GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    2. CellName:CascodeStageNPair
    PININFO:DRAIN1(I/I)SOURCE1(I/O)DRAIN2(I/I)SOURCE2(I/O)VBIAS(B)
    GND(P)
    Description:APairofNMOSCascode
    ************************************************************************
    *Library Name: DATASET *Cell Name: CascodeStageNPair *View Name: schematic
    ************************************************************************
    .SUBCKT CascodeStageN DRAIN1 SOURCE1 DRAIN2 SOURCE2 VBIAS GND
    *.PININFO DRAIN:B GND:B SOURCE:B VBIAS:B
    MM0 DRAIN1 VBIAS SOURCE1 GND nch mac l=30n w=100n m=1 nf=1
    MM1 DRAIN2 VBIAS SOURCE2 GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    3. CellName:CascodeStageP
    PININFO:DRAIN(I/O)SOURCE(I/I)VBIAS(B)VDD(P)
    Description:SinglePMOSCascode
    *Library Name: DATASET *Cell Name: CascodeStageP *View Name: schematic
    ************************************************************************
    .SUBCKT CascodeStageP DRAIN SOURCE VBIAS VDD
    *.PININFO DRAIN:B SOURCE:B VBIAS:B VDD:B
    MM0 DRAIN VBIAS SOURCE VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    4. CellName:CascodeStagePPair
    PININFO:DRAIN1(I/O)SOURCE1(I/I)DRAIN2(I/O)SOURCE2(I/I)VBIAS(B)
    VDD(P)
    Description:APairofPMOSCascode
    *Library Name: DATASET *Cell Name: CascodeStagePPair *View Name: schematic
    ************************************************************************
    .SUBCKT CascodeStageP DRAIN1 SOURCE1 DRAIN2 SOURCE2 VBIAS VDD
    *.PININFO DRAIN:B SOURCE:B VBIAS:B VDD:B
    MM0 DRAIN VBIAS SOURCE VDD pch mac l=30n w=100n m=1 nf=1
    MM1 DRAIN VBIAS SOURCE VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    5. CellName:DiodeConnectedN
    PININFO:DRAIN(I/I)GND(P)
    Description:DiodeConnectedSignleNMOS
    ************************************************************************
    *Library Name: DATASET *Cell Name: DiodeConnectedN *View Name: schematic
    ************************************************************************
    .SUBCKT DiodeConnectedN DRAIN GND
    *.PININFO DRAIN:B GND:B VIN:B
    MM0 DRAIN DRAIN GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    6. CellName:DiodeConnectedP
    PININFO:DRAIN(I/O)VDD(P)
    Description:DiodeConnectedSignlePMOS
    ************************************************************************
    *Library Name: DATASET *Cell Name: DiodeConnectedP *View Name: schematic
    ************************************************************************
    .SUBCKT CommonSourceN DRAIN VDD
    *.PININFO DRAIN:B GND:B VIN:B
    MM0 DRAIN DRAIN VDD VDD nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    7. CellName:CommonSourceN
    PININFO:DRAIN(I/I)VIN(V)GND(P)
    Description:commonsourcesingleNMOSamplifier
    ************************************************************************
    *Library Name: DATASET *Cell Name: CommonSourceN *View Name: schematic
    ************************************************************************
    .SUBCKT CommonSourceN DRAIN VIN GND
    *.PININFO DRAIN:B GND:B VIN:B
    MM0 DRAIN VIN GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    8. CellName:CommonSourceP
    PININFO:DRAIN(I/O)VIN(V)VDD(P)
    Description:commonsourcesinglePMOSamplifier
    ************************************************************************
    *Library Name: DATASET *Cell Name: CommonSourceP *View Name: schematic
    ************************************************************************
    .SUBCKT CommonSourceP DRAIN VIN VDD
    *.PININFO DRAIN:B VDD:B VIN:B
    MM0 DRAIN VIN VDD VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    9. CellName:CurrentMirrorCSN
    PININFO:O1(I/I)O2(I/I)VBIAS(B)GND(P)
    Description:CascodeCurrentMirrorbasedonNMOSwithsinglebias
    ************************************************************************
    *Library Name: DATASET *Cell Name: CommonSourceP *View Name: schematic
    ************************************************************************
    .SUBCKT CommonSourceP DRAIN VIN VDD
    *.PININFO DRAIN:B VDD:B VIN:B
    MM0 DRAIN VIN VDD VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    10. CellName:CurrentMirrorCSNB
    PININFO:O1(I/I)O2(I/I)VBIAS1(B)VBIAS2(B)GND(P)
    Description:CascodeCurrentMirrorbasedonNMOSwithtwoseperatebias
    ************************************************************************
    *Library Name: DATASET *Cell Name: CurrentMirrorCSN *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSN O1 O2 VBIAS GND
    *.PININFO GND:B O1:B O2:B VBIAS:B
    MM3 O2 VBIAS net14 GND nch mac l=30n w=100n m=1 nf=1
    MM2 O1 VBIAS net10 GND nch mac l=30n w=100n m=1 nf=1
    MM1 net14 O1 GND GND nch mac l=30n w=100n m=1 nf=1
    MM0 net10 O1 GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    11. CellName:CurrentMirrorCSNS
    PININFO:O1(I/I)O2(I/I)GND(P)
    Description:CascodeCurrentMirrorbasedonNMOSwithoutseperatebias, two
    selfconnectedcurrentmirror
    *Library Name: DATASET *Cell Name: CurrentMirrorCSNB *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSNB O1 O2 VBIAS1 VBIAS2 GND
    *.PININFO GND:B O1:B O2:B VBIAS:B
    MM3 O2 VBIAS1 net14 GND nch mac l=30n w=100n m=1 nf=1
    MM2 O1 VBIAS1 net10 GND nch mac l=30n w=100n m=1 nf=1
    MM1 net14 VBIAS2 GND GND nch mac l=30n w=100n m=1 nf=1
    MM0 net10 VBIAS2 GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    12. CellName:CurrentMirrorCSP
    PININFO:O1(I/O)O2(I/O)VBIAS(B)VDD(P)
    Description:CascodeCurrentMirrorbasedonPMOSwithsinglebias
    ************************************************************************
    *Library Name: DATASET *Cell Name: CurrentMirrorCSNBS *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSNBS O1 O2 GND
    *.PININFO GND:B O1:B O2:B VBIAS:B
    MM3 O2 O1 net14 GND nch mac l=30n w=100n m=1 nf=1
    MM2 O1 O1 net10 GND nch mac l=30n w=100n m=1 nf=1
    MM1 net14 net10 GND GND nch mac l=30n w=100n m=1 nf=1
    MM0 net10 net10 GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    13. CellName:CurrentMirrorCSPB
    PININFO:O1(I/O)O2(I/O)VBIAS1(B)VBIAS2(B)VDD(P)
    Description:CascodeCurrentMirrorbasedonPMOSwithtwoseperatebias
    *Library Name: DATASET *Cell Name: CurrentMirrorCSP *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSP O1 O2 VBIAS VDD
    *.PININFO O1:B O2:B VBIAS:B VDD:B
    MM3 net14 O1 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM2 net15 O1 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM5 O2 VBIAS net14 VDD pch mac l=30n w=100n m=1 nf=1
    MM4 O1 VBIAS net15 VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    14. CellName:CurrentMirrorCSPS
    PININFO:O1(I/O)O2(I/O)VDD(P)
    Description:CascodeCurrentMirrorbasedonPMOSwithoutseperatebias, two
    selfconnectedcurrentmirror
    *Library Name: DATASET *Cell Name: CurrentMirrorCSPB *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSPB O1 O2 VBIAS1 VBIAS2 VDD
    *.PININFO O1:B O2:B VBIAS:B VDD:B
    MM3 net14 VBIAS2 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM2 net15 VBIAS2 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM5 O2 VBIAS1 net14 VDD pch mac l=30n w=100n m=1 nf=1
    MM4 O1 VBIAS1 net15 VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    15. CellName:CurrentMirrorN
    PININFO:O1(I/I)O2(I/I)GND(P)
    Description:SimpleCurrentMirrorbasedonNMOS
    *Library Name: DATASET *Cell Name: CurrentMirrorCSPBS *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorCSPBS O1 O2 VDD
    *.PININFO O1:B O2:B VBIAS:B VDD:B
    MM3 net14 net15 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM2 net15 net15 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM5 O2 O1 net14 VDD pch mac l=30n w=100n m=1 nf=1
    MM4 O1 O1 net15 VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    16. CellName:CurrentMirrorP
    PININFO:O1(I/O)O2(I/O)VDD(P)
    Description:SimpleCurrentMirrorbasedonPMOS
    *Library Name: DATASET *Cell Name: CurrentMirrorN *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorN O1 O2 GND
    *.PININFO GND:B O1:B O2:B
    MM1 O2 O1 GND GND nch mac l=30n w=100n m=1 nf=1
    MM0 O1 O1 GND GND nch mac l=30n w=100n m=1 nf=1
    ENDS
    ************************************************************************
    17. CellName:CurrentSourceN
    PININFO:DRAIN(I/I)VBIAS(B)GND(P)
    Description:BiasControlCurrentSourcebasedonNMOS
    *Library Name: DATASET *Cell Name: CurrentMirrorP *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentMirrorP O1 O2 VDD
    *.PININFO O1:B O2:B VDD:B
    MM3 O2 O1 VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM2 O1 O1 VDD VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    18. CellName:CurrentSourceP
    PININFO:DRAIN(I/O)VBIAS(B)GND(P)
    Description:BiasControlCurrentSourcebasedonPMOS
    ************************************************************************
    *Library Name: DATASET *Cell Name: CurrentSourceN *View Name: schematic
    ************************************************************************
    .SUBCKT CurrentSourceN DRAIN VBIAS GND
    *.PININFO DRAIN:B GND:B VBIAS:B
    MM0 DRAIN VBIAS GND GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    19. CellName:DifferentialPairN
    PININFO:O1(I/I)O2(I/I)VBIAS(B)VIN(V)VIP(V)GND(P)
    Description:DifferentialPairbasedonNMOS,withtailbias
    ************************************************************************
    *Library Name: DATASET *Cell Name: DifferentialPairN *View Name: schematic
    ************************************************************************
    .SUBCKT DifferentialPairN O1 O2 VBIAS VIN VIP GND
    *.PININFO GND:B O1:B O2:B VBIAS:B VIN:B VIP:B
    MM2 O2 VIP net2 GND nch mac l=30n w=100n m=1 nf=1
    MM1 net2 VBIAS GND GND nch mac l=30n w=100n m=1 nf=1
    MM0 O1 VIN net2 GND nch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    20. CellName:DifferentialPairP
    PININFO:O1(I/O)O2(I/O)VBIAS(B)VIN(V)VIP(V)VDD(P)
    Description:DifferentialPairbasedonPMOS,withtailbias
    ************************************************************************
    *Library Name: DATASET *Cell Name: DifferentialPairP *View Name: schematic
    ************************************************************************
    .SUBCKT DifferentialPairP O1 O2 VBIAS VIN VIP VDD
    *.PININFO O1:B O2:B VBIAS:B VDD:B VIN:B VIP:B
    MM1 O2 VIP net1 VDD pch mac l=30n w=100n m=1 nf=1
    MM2 net1 VBIAS VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM0 O1 VIN net1 VDD pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    21. CellName:DifferentialPairPBS
    PININFO:O1(I/O)O2(I/O)VBIAS(B)VIN(V)VIP(V)VDD(P)
    Description:DifferentialPairbasedonPMOS(BulkconnectedtoSource),with
    tailbias
    ************************************************************************
    *Library Name: DATASET *Cell Name: DifferentialPairPBS *View Name: schematic
    ************************************************************************
    .SUBCKT DifferentialPairP O1 O2 VBIAS VIN VIP VDD
    *.PININFO O1:B O2:B VBIAS:B VDD:B VIN:B VIP:B
    MM1 O2 VIP net1 O2 pch mac l=30n w=100n m=1 nf=1
    MM2 net1 VBIAS VDD VDD pch mac l=30n w=100n m=1 nf=1
    MM0 O1 VIN net1 O1 pch mac l=30n w=100n m=1 nf=1
    .ENDS
    ************************************************************************
    22. CellName:R
    PININFO:O1(P)O2(P)
    Description:Resistor
    ************************************************************************
    *Library Name: DATASET *Cell Name: R *View Name: schematic
    ************************************************************************
    .SUBCKT R O1 O2
    *.PININFO O1:B O2:B
    XR0 O1 O2 rnodwo l=10u w=2u m=1
    .ENDS
    ************************************************************************
    23. CellName:C
    PININFO:O1(V)O2(V)
    Description:Capacitor
    ************************************************************************
    *Library Name: DATASET *Cell Name: C *View Name: schematic
    ************************************************************************
    .SUBCKT C O1 O2
    *.PININFO O1:B O2:B
    XC0 O1 O2 cfmom 2t nr=24 lr=1u w=50n s=50n stm=1 spm=3 m=1
    .ENDS
    ************************************************************************
    24. CellName:CapFeadback
    PININFO:Vout(V)Vin(V)mid(V)
    Description:FeadbacknetswithtwoCapacitors
    ************************************************************************
    *Library Name: DATASET *Cell Name: Cap Feadback *View Name: schematic
    ************************************************************************
    .SUBCKT C Vout Vin mid
    *.PININFO Vout:B Vin:B mid:B
    XC0 Vout mid cfmom 2t nr=24 lr=1u w=50n s=50n stm=1 spm=3 m=1
    XC1 Vin mid cfmom 2t nr=24 lr=1u w=50n s=50n stm=1 spm=3 m=1
    .ENDS


    [Experience rule ]
    A part from this there are also some basic things you should know:
    1.The TailBias1 have been included in the DifferentialPairN/P/PBS
    subcircuit, you needn't to set the tail bias separately. But you should check
    that only Differential Input need the simple mirror TailBias.
    2.Most times, the PMOS input may matches the NMOS current mirror. So,
    usually please don't match the PMOS input with a PMOS current mirror.
    3.Don't use the MOSFET and R/C directly, use the subcircuits 1-23

    [CoT Task Decomposition Prompt]
    
    For the generation step, Please follow these steps:
    1. Step1: According to the stage number and then select the appropriate
    basic components from the library for each stage;
    2. Step2: Connect the select blocks to form the final circuits. Note that
    the current flow ports(I/O) must be matched by corresponding current
    inflow ports(I/I) or (P) during the connection process. Generate the
    final netlist, the netlist should Start with "'***NetlistStart***"' and
    end with "'***NetlistEnd***"', and the terminal type should also
    be listed including(I/I),(I/O),(V),(B),(P); (V) is the vin/vout; (B) is
    the bias; (P) is the power;

    [User Design Specification]
    {user_query}

    Generate the netlist satisfying the above query.

    Make sure to wrap the generated netlist between the markers:
    ***NetlistStart***
    <your netlist here>
    ***NetlistEnd***
    """
    return sonnet_3_5.invoke(prompt.format(user_query=input))


@tool("input_validation", return_direct=True)
def input_validation(input:str)->str:
    """
    Checks whether the user's analog circuit design input is complete and logically consistent.

    Args:
        input (str): Circuit specification provided in structured or block-based format.

    Returns:
        str: A structured report indicating input format, validity, issues, and suggestions.
    """

    prompt = """
    You are a senior analog circuit design assistant. Your job is to validate whether a given design specification is complete and logically consistent.

    Users may provide design requirements in two formats:
    1. **Structured Field-Based Format**:
    Contains:
    - Stage Numbers
    - Compensation Type (None / Miller / Ahuja / etc)
    - Feedback Type (Inverting / Non-inverting) and Network (Resistive / Capacitive / None)
    - Input and Output Signal Types (Single-ended / Differential)
    - Input Transistor Type (NMOS / PMOS / PMOS B2S)
    - Topology (Common Source / Folded / Telescopic)
    - Load Type (Simple Mirror / Wide-Swing Mirror)
    - Tail Bias (Ground / Current Source / Simple Mirror)

    2. **Block-Based Format**:
    Example:
    - Input Stage: 1
    - Input blocks: DifferentialPairN / P / PBS
    - Other blocks: list of other subcircuits
    - Max block number: Total circuit stages or blocks

    ---

    NOTES:
    - Differential input → Single-ended output is valid and common.
    - PMOS input stages may use NMOS mirrors or fold into NMOS paths — this is valid.
    - In block-based format, ensure the block list includes a valid input block and enough stages for design goals.
    - Warn if essential stage elements like load or compensation are missing or incompatible.
    - Differential output can be achieved in single-stage designs (e.g., telescopic topology with wide-swing mirror). Do not assume a second stage is required based on output type alone.

    Your task:
    1. Detect which format the input is using.
    2. Check for missing or inconsistent logic in either format.
    3. Return a structured report.

    [User Design Input]
    {user_input}

    Return the response in this format:
    INPUT VERIFICATION REPORT:
    - Format: STRUCTURED / BLOCK-BASED
    - Verdict: VALID / INVALID
    - Issues: [list any missing or logically inconsistent fields or block usages]
    - Suggestions: [recommend how to fix invalid or missing elements for that input type]
    """
    return sonnet_3_7.invoke(prompt.format(user_input=input))


@tool("output_validation",return_direct=True)
def output_validation(input : str) -> str :
    """
    Validates the correctness of an analog circuit netlist using predefined design and connectivity rules.

    Args:
        input (str): Full circuit specification including block names and SPICE-style netlist.

    Returns:
        str: A validation report with pass/fail verdict, rule violations, and justification.
    """

    prompt = """
    You are a circuit validation expert. Validate the analog circuit described in the input using the RULES provided below.

    Before applying the rules, consider the following:

    BLOCK ROLE DEFINITIONS:
    - DifferentialPairN: NMOS differential input stage with built-in tail bias. May implement common source functionality if single-ended output used.
    - DifferentialPairP / PBS: PMOS differential pair with bulk-to-source configuration and internal biasing.
    - CascodeStageNPair: NMOS cascode stage used for telescopic and folded topologies.
    - CurrentMirrorP / CSP / CSPB: PMOS current mirrors (simple or wide-swing). Used to load NMOS differential stages.
    - CurrentMirrorN: NMOS mirror typically used as tail current source for PMOS input stages.
    - CommonSourceN: NMOS amplifier used in second-stage gain (e.g., Ahuja compensation).
    - C: Capacitor block used in Miller/Ahuja compensation.
    - CurrentSourceP/N: Only used when specified in multi-stage or compensation designs, not with DifferentialPair blocks.

    TOPOLOGY NOTES:
    - Common Source input stages may be implemented using a DifferentialPairN block with only one output.
    - "net01"-style shared nodes connecting I/O and I/I terminals between blocks are valid current links.
    - Top-level .SUBCKT ports like Vbiasn, Vout, etc., are considered connected if passed into subblocks.

    RULES:

    Block Type Checks:
    1. The input stage must be one of: DifferentialPairN, DifferentialPairP, or DifferentialPairPBS. These may represent common source, folded, or telescopic topologies depending on context.
    2. Do not use raw MOSFETs or discrete Rs/Cs directly. Only use subcircuits from the provided block library.
    3. Tail bias is included in DifferentialPairN, P, PBS blocks. Do not externally add CurrentSourceN/P unless part of output/complementary stage.
    4. NMOS differential inputs (e.g., DifferentialPairN) may be loaded with PMOS mirrors (CurrentMirrorP, CSP, CSPB). This is valid.
    5. PMOS differential inputs (PBS) may fold into NMOS cascodes or use CurrentMirrorN. This is valid in folded cascode topologies.

    Connection Checks:
    1. I/I (input current) terminals must connect to valid I/O (output current) or P (power) terminals.
    2. I/O (current output) terminals must connect to valid I/I or P terminals.
    3. V (voltage) terminals must connect to other V terminals or passive elements like C.
    4. B (bias) terminals must be connected and not left floating — top-level port passing counts as connected.
    5. P (power) terminals must connect to VDD or GND correctly.
    6. No terminal should be floating — all terminals must be part of valid nets.
    7. In multi-stage circuits, outputs from stage N must feed inputs of stage N+1 appropriately.
    8. Feedback components like C must connect valid voltage nodes (e.g., output ↔ input).

    [USER CIRCUIT INPUT]
    {input_text}

    ---

    Return the result in this format:
    VALIDATION REPORT:
    - Verdict: PASS / FAIL
    - Violated Rules: [list rule numbers]
    - Justification: [Explain why the design passes or fails based on the netlist and description. Be specific.]
    """
    return sonnet_3_7.invoke(prompt.format(input_text=input))