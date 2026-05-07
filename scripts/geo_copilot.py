### my worst nightmare 
## Note to self:
## 1- Erase lines one by one when making modification and do run upon each change to make sure tool does not break
## 2- Figure out how to handle tkinter not responding state (causes Arc pro to crash) ------ CRITICAL
## 3-
## 4- System prompt not optimal in this version, improve it
## 5-

#################### DO NOT SHARE CODE ---------- API KEY IS EXPOSED --------------- 

import arcpy
import json
import sys
import ast
from openai import OpenAI
import requests
import tkinter as tk
from tkinter import ttk, messagebox

def get_active_map():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    mp = aprx.activeMap
    return mp

def fields_info(layer):
    out = []
    for f in arcpy.ListFields(layer):
        out.append({"name": f.name, "type": f.type})
    return out

def get_layer_metadata(l):
    d = arcpy.Describe(l)
    #print(d)
    info = dict()
    info["name"] = l.name
    info["geometry_type"] = getattr(d, "shapeType", None) if hasattr(d, "shapeType") else None
    sr = getattr(d, "spatialReference", None)
    info["spatial_reference"] = {"name": sr.name, "wkid": getattr(sr, "factoryCode", None)}
    info["fields"] = fields_info(l)
    return info

def get_active_layers():
    mp = get_active_map()
    units = None
    if mp.spatialReference:
        units = mp.spatialReference.linearUnitName or mp.spatialReference.angularUnitName
    layers_meta = []
    for l in mp.listLayers():
        layers_meta.append(get_layer_metadata(l))
    return layers_meta, units

def call_gpt5(system_prompt, user_message):                 ###### API Key K leye env set krna upon final delivery ------- Critical
    client = OpenAI(api_key="Your OpenAI API Key Here")
    resp = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role":"system","content":system_prompt},
                  {"role":"user","content":user_message}]
    )
    content = (resp.choices[0].message.content or "").strip()
    #print(resp)
    #print(content)
    if not content:
        raise RuntimeError("Empty content from GPT-5 response.")
    usage = getattr(resp, "usage", None)
    tokens = getattr(usage, "total_tokens", None) if usage else None
    return content, tokens

def call_llama3(system_prompt, user_message):
    url = "http://localhost:11434/api/chat"   
    model = "llama3.1:8b"                      

    r = requests.post(
        url,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message}
            ],
            "stream": False
        },
        timeout=400
    )
    #print(r)

    if r.status_code >= 400:
        raise RuntimeError(f"Llama3 HTTP {r.status_code}: {r.text}")

    data = r.json() or {}
    #print(data)
    content = (data.get("message", {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Empty content from Llama3 response.")

    try:
        tokens = int((data.get("eval_count") or 0) + (data.get("prompt_eval_count") or 0))
    except Exception:
        tokens = None

    return content, tokens

def call_model(system_prompt, user_message, model_choice):
    if (model_choice).upper() == "LLAMA3":
        return call_llama3(system_prompt, user_message)
    return call_gpt5(system_prompt, user_message)

def show_gui_window(system_prompt_text, user_message_text, model_choice_str):
    root = tk.Tk()
    root.title("GIS Copilot")
    root.geometry("1000x700")

    result = {"approved": False, "commands": None}

    control_frame = ttk.Frame(root)
    control_frame.pack(fill="x", padx=10, pady=10, side="bottom")
    
    token_lbl = ttk.Label(control_frame, text="Tokens: n/a")
    token_lbl.pack(side="left")
    
    btn_exec = ttk.Button(control_frame, text="Execute", state="disabled")
    btn_exec.pack(side="right", padx=(5, 0))
    
    btn_quit = ttk.Button(control_frame, text="Quit", command=root.destroy)
    btn_quit.pack(side="right")
    
    btn_send = ttk.Button(control_frame, text="Send to LLM")
    btn_send.pack(side="right", padx=(0, 5))

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=10, pady=(10, 5))

    tab1 = ttk.Frame(nb)
    nb.add(tab1, text="Prompts")
    
    prompt_txt = tk.Text(tab1, wrap="word", state="normal")
    prompt_txt.pack(fill="both", expand=True)
    prompt_txt.insert("1.0", f"=== SYSTEM PROMPT ===\n{system_prompt_text}\n\n=== USER MESSAGE ===\n{user_message_text}")
    prompt_txt.config(state="disabled")

    tab2 = ttk.Frame(nb)
    nb.add(tab2, text="Results")
    
    container = ttk.Frame(tab2)
    container.pack(fill="both", expand=True)
    container.grid_rowconfigure(0, weight=1, uniform="equal")
    container.grid_rowconfigure(1, weight=1, uniform="equal")
    container.grid_columnconfigure(0, weight=1)
    
    #### Do not modify in this version or GUI will start acting wierd
    top_frame = ttk.LabelFrame(container, text="LLM Output")
    top_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
    output_txt = tk.Text(top_frame, wrap="word", state="disabled")
    output_txt.pack(fill="both", expand=True)
    
    #### Do not modify in this version or GUI will start acting wierd
    bottom_frame = ttk.LabelFrame(container, text="Parsed Workflow")
    bottom_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
    workflow_list = tk.Listbox(bottom_frame)
    workflow_list.pack(fill="both", expand=True)

    def send_request():
        btn_send.config(state="disabled")
        btn_exec.config(state="disabled")
        
        # Clear previous results
        output_txt.config(state="normal")
        output_txt.delete("1.0", "end")
        output_txt.config(state="disabled")
        workflow_list.delete(0, "end")
        token_lbl.config(text="Tokens: ...")

        # First: get response from model
        try:
            content, tokens = call_model(system_prompt_text, user_message_text, model_choice_str)
        except Exception as e:
            # If the HTTP / model call itself fails, there is no content to show
            messagebox.showerror("Error", f"Model request failed:\n{str(e)}")
            btn_send.config(state="normal")
            return

        # Second: ALWAYS show raw LLM output, even if it’s wrong
        output_txt.config(state="normal")
        output_txt.insert("1.0", content)
        output_txt.config(state="disabled")
        token_lbl.config(text=f"Tokens: {tokens if tokens else 'n/a'}")

        # Third: try to parse it as a Python list of strings
        try:
            cmds = ast.literal_eval(content)
            if not isinstance(cmds, list) or not all(isinstance(x, str) for x in cmds):
                raise ValueError("Output is not a list of strings")

            # If parsing is OK, populate workflow list and enable Execute
            workflow_list.delete(0, "end")
            for i, cmd in enumerate(cmds, 1):
                workflow_list.insert("end", f"{i}. {cmd}")

            result["commands"] = cmds
            btn_exec.config(state="normal")
            nb.select(tab2)
        except Exception as e:
            # Parsing failed: keep raw output visible, but no commands to execute
            result["commands"] = None
            messagebox.showerror(
                "Error",
                f"Failed to parse LLM response into commands.\n\n"
                f"Details:\n{str(e)}\n\n"
                f"The raw response is shown above for inspection."
            )
        finally:
            btn_send.config(state="normal")

    def execute_workflow():
        result["approved"] = True
        root.destroy()

    btn_send.config(command=send_request)
    btn_exec.config(command=execute_workflow)

    root.mainloop()
    return result["approved"], result["commands"]

ALLOWED_TOOLS = {
    "Buffer_analysis": {
        "signature": "Buffer_analysis in_features out_feature_class buffer_distance_or_field {line_side} {line_end_type} {dissolve_option} {dissolve_field} {method}",
        "example":   'Buffer_analysis BikeShops_Geocoded_1 BikeShops_Buffer500m_ai "500 Meters" FULL ROUND ALL # PLANAR',
        "out_index": 2,
    },
    "Clip_analysis": {
        "signature": "Clip_analysis in_features clip_features out_feature_class {cluster_tolerance}",
        "example":   "Clip_analysis Roads CityLimits Roads_Clipped_ai",
        "out_index": 3,
    },
    "Intersect_analysis": {
        "signature": "Intersect_analysis in_features out_feature_class {join_attributes} {cluster_tolerance} {output_type}",
        "example":   'Intersect_analysis "Parcels;Schools_Buffer500m_ai" ParcelsNearSchools_ai ALL # INPUT',
        "out_index": 2,
    },
    "Dissolve_management": {
        "signature": "Dissolve_management in_features out_feature_class {dissolve_field} {statistics_fields} {multi_part} {unsplit_lines}",
        "example":   'Dissolve_management Blocks Blocks_Dissolved_ai "TRACT_ID" # MULTI_PART DISSOLVE_LINES',
        "out_index": 2,
    },
    "SelectLayerByAttribute_management": {
        "signature": "SelectLayerByAttribute_management in_layer_or_view {selection_type} {where_clause}",
        "example":   'SelectLayerByAttribute_management Schools NEW_SELECTION "LEVEL = \'Elementary\'"',
        "out_index": None, 
    },
    "SelectLayerByLocation_management": {
        "signature": "SelectLayerByLocation_management in_layer {overlap_type} select_features {search_distance} {selection_type} {invert_spatial_relationship}",
        "example":   "SelectLayerByLocation_management Schools INTERSECT Parcels # NEW_SELECTION",
        "example":   'SelectLayerByLocation_management Schools WITHIN_A_DISTANCE hospitals "100 Meters" NEW_SELECTION',
        "out_index": None,
    },
    "CopyFeatures_management": {
        "signature": "CopyFeatures_management in_features out_feature_class {config_keyword}",
        "example":   "CopyFeatures_management Schools Schools_Selected_ai",
        "out_index": 2,
    },
    "SpatialJoin_analysis": {
        "signature": "SpatialJoin_analysis target_features join_features out_feature_class {join_operation} {join_type} {field_mapping} {match_option} {search_radius} {distance_field_name}",
        "example":   'SpatialJoin_analysis Parcels Schools Parcels_Joined_ai JOIN_ONE_TO_ONE KEEP_ALL # WITHIN_A_DISTANCE "500 Meters"',
        "out_index": 3,
    },
    "Erase_analysis": {
        "signature": "Erase_analysis in_features erase_features out_feature_class {cluster_tolerance}",
        "example":   "Erase_analysis Parcels Floodplain Parcels_NoFlood_ai",
        "out_index": 3,
    },
    "Union_analysis": {
        "signature": "Union_analysis in_features out_feature_class {join_attributes} {cluster_tolerance} {gaps}",
        "example":   'Union_analysis "Zoning;Parcels" ZoningParcels_Union_ai ALL # GAPS',
        "out_index": 2,
    },
    "AddField_management": {
        "signature": "AddField_management in_table field_name field_type {field_precision} {field_scale} {field_length} {field_alias} {field_is_nullable} {field_is_required} {field_domain}",
        "example":   "AddField_management Communities AreaHa DOUBLE # # # # NULLABLE NON_REQUIRED #",
        "out_index": None,
    },

    "CalculateField_management": {
        "signature": "CalculateField_management in_table field expression {expression_type} {code_block}",
        "example":   'CalculateField_management Communities AreaHa "(!shape.area@SQUAREMETERS! / 10000)" "PYTHON3" #',
        "out_index": None,
    },
    
}

SYSTEM_PROMPT = """You are an Expert GIS Developer. Turn the user’s request + project context into a sequence of ArcGIS **command-line** geoprocessing calls to be executed with arcpy.Command().

OUTPUT FORMAT:
- Return ONLY a Python list literal of strings. No prose, no code fences, no JSON objects.

STRICT RULES:
- Do not output ```python ......``` or any other text.
- Use ONLY the tools listed in **Allowed Tools** below. If a needed tool is missing, return ["ERROR ToolNotAllowed <ToolName>"].
- Use ONLY layers and parameters present in the provided context. If something is missing, return ["ERROR MissingInput <Name>"].
- Quote any distance WITH UNITS as a single token, e.g. "500 Meters", "1000 Feet".
- For every tool that creates a dataset, the output name MUST start with `ai_`. Selection tools do not create outputs.
- Maintain positional parameter order exactly as shown in signatures and examples. Use `#` for omitted optional parameters when examples do.
- Do NOT auto-project. If CRS mismatch blocks an operation and the user didn’t request projection, return ["ERROR CRSConflict <A> <CRS_A> vs <B> <CRS_B>"].

Tools:
1) Buffer_analysis in_features out_feature_class buffer_distance_or_field {line_side} {line_end_type} {dissolve_option} {dissolve_field} {method}
   → Buffer_analysis BikeShops_Geocoded_1 BikeShops_Buffer500m_ai "500 Meters" FULL ROUND ALL # PLANAR
2) Clip_analysis in_features clip_features out_feature_class {cluster_tolerance}
   → Clip_analysis Roads CityLimits Roads_Clipped_ai
3) Intersect_analysis in_features out_feature_class {join_attributes} {cluster_tolerance} {output_type}
   → Intersect_analysis "Parcels;Schools_Buffer500m_ai" ParcelsNearSchools_ai ALL # INPUT
4) Dissolve_management in_features out_feature_class {dissolve_field} {statistics_fields} {multi_part} {unsplit_lines}
   → Dissolve_management Blocks Blocks_Dissolved_ai "TRACT_ID" # MULTI_PART DISSOLVE_LINES
5) SelectLayerByAttribute_management in_layer_or_view {selection_type} {where_clause}
   → SelectLayerByAttribute_management Schools NEW_SELECTION "LEVEL = 'Elementary'"
   → SelectLayerByAttribute_management Schools CLEAR_SELECTION
6) SelectLayerByLocation_management in_layer {overlap_type} select_features {search_distance} {selection_type} {invert_spatial_relationship}
   → SelectLayerByLocation_management Schools WITHIN_A_DISTANCE BikeShops_Buffer500m_ai # NEW_SELECTION
   → SelectLayerByLocation_management Schools INTERSECT Parcels # ADD_TO_SELECTION
7) CopyFeatures_management in_features out_feature_class {config_keyword}
   → CopyFeatures_management Schools Schools_Selected_ai
8) SpatialJoin_analysis target_features join_features out_feature_class {join_operation} {join_type} {field_mapping} {match_option} {search_radius} {distance_field_name}
   → SpatialJoin_analysis Parcels Schools Parcels_Joined_ai JOIN_ONE_TO_ONE KEEP_ALL # WITHIN_A_DISTANCE "500 Meters"
9) Erase_analysis in_features erase_features out_feature_class {cluster_tolerance}
   → Erase_analysis Parcels Floodplain Parcels_NoFlood_ai
10) Union_analysis in_features out_feature_class {join_attributes} {cluster_tolerance} {gaps}
   → Union_analysis "Zoning;Parcels" ZoningParcels_Union_ai ALL # GAPS
11) AddField_management in_table field_name field_type {field_precision} {field_scale} {field_length} {field_alias} {field_is_nullable} {field_is_required} {field_domain}
    → AddField_management Communities AreaHa DOUBLE # # # # NULLABLE NON_REQUIRED #
12) CalculateField_management in_table field expression {expression_type} {code_block}
    → CalculateField_management Communities AreaHa "(!shape.area@SQUAREMETERS! / 10000)" "PYTHON3" #
"""

user_query = arcpy.GetParameterAsText(0)
model_choice = arcpy.GetParameterAsText(1) 

arcpy.env.overwriteOutput = True
ws = arcpy.env.workspace or arcpy.mp.ArcGISProject("CURRENT").defaultGeodatabase
scratch_gdb = arcpy.env.scratchGDB
scratch_folder = arcpy.env.scratchFolder

active_layers_meta, map_units = get_active_layers()

context_payload = dict()
context_payload["user_query"] = user_query
context_payload["environments"] = {
    "workspace": ws,
    "scratchGDB": scratch_gdb,
    "scratchFolder": scratch_folder,
    "overwriteOutput": True,
    "map_units": map_units,
    # removed: "extent"
    "snapRaster": arcpy.env.snapRaster if arcpy.env.snapRaster else None,
}
context_payload["active_layers"] = active_layers_meta
context_payload["allowed_tools"] = ALLOWED_TOOLS
context_payload["naming_policy"] = 'append "_ai" to all outputs'
context_payload["spatial_reference_policy"] = "Do not auto-project; retain source SRS unless user explicitly requests."

USER_MESSAGE = json.dumps(context_payload, indent=2)

approved, commands_list = show_gui_window(SYSTEM_PROMPT, USER_MESSAGE, model_choice)

if not approved or commands_list is None:
    arcpy.AddWarning("No valid workflow. Nothing executed.")
    sys.exit(0)

for cmd in commands_list:
    try:
        arcpy.Command(cmd)
    except Exception as exc:
        arcpy.AddError(f"Command failed: {exc}")
        raise