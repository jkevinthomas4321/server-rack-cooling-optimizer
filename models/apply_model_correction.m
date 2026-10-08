% apply_model_correction.m
% Applies the October 2026 model correction to server_cooling_loop_v2_working.slx.
% The script records every parameter that was changed, so the change to the binary
% .slx file can be reviewed as text. It has already been applied to the committed
% model; running it again on that model only rewrites the same values.
%
% Sources for the values are listed in the README ("Model Parameters and Sources").

model = 'server_cooling_loop_v2_working';
cd(fileparts(mfilename('fullpath')));
load_system(model);

pump     = [model '/Centrifugal Pump' newline '(TL)'];
pipe     = [model '/Pipe (TL)'];
chamber  = [model '/Constant Volume' newline 'Chamber (TL)'];
inlet    = [model '/Reservoir (TL)'];
outlet   = [model '/Reservoir (TL)1'];
cpu      = [model '/Thermal Mass'];
coldplate = [model '/Cold Plate Flow Resistance (TL)'];

T_SUPPLY_K = '318.15';   % 45 degC coolant supply (OCP "Group 1" 40-45 degC, Wakefield test condition)

%% 1. Pump: Laing D5-class 12 V circulation pump, tabulated at 4800 rpm
% Head/power read from the Xylem/Laing D5 catalogue BR-19B (speed setting 5), anchored to the
% published 3.9 m shut-off head, 1500 l/h maximum flow and 23 W maximum power.
% The catalogue gives electrical input power. It is used as the block's brake power because the
% D5 is a wet-rotor pump, so its motor losses also end up in the coolant (assumption).
set_param(pump, 'pump_parameterization', ...
    'fluids.thermal_liquid.pumps_motors.enum.CentrifugalPumpParameterization.Table1D');
set_param(pump, 'flow_rate_1D_TLU', '[0, 5, 10, 15, 20, 25]', 'flow_rate_1D_TLU_unit', 'lpm');
set_param(pump, 'head_1D_TLU', '[3.9, 3.7, 3.3, 2.6, 1.6, 0.1]', 'head_1D_TLU_unit', 'm');
set_param(pump, 'power_1D_TLU', '[17, 19, 20.5, 22, 23, 23]', 'power_1D_TLU_unit', 'W');
set_param(pump, 'omega_ref_1D', '4800', 'omega_ref_1D_unit', 'rpm');
set_param(pump, 'area', '0.00005');   % 8 mm ports, same as the tubing

%% 2. Boundaries: equal pressure, so the flow is driven by the pump only
set_param(inlet,  'reservoir_pressure', '1.5', 'reservoir_temperature', T_SUPPLY_K);
set_param(outlet, 'reservoir_pressure', '1.5', 'reservoir_temperature', T_SUPPLY_K);

%% 3. Cold plate pressure drop: new Flow Resistance (TL) between the pipe and the chamber
% 29.3 kPa at 2 L/min per cold plate (OCP OAI liquid cooling guidelines, section 6.3.3:
% 17 psi at 2 LPM per path, about 50 % of it in two cold plates in series).
if getSimulinkBlockHandle(coldplate) == -1
    pipe_ports    = get_param(pipe, 'PortHandles');
    chamber_ports = get_param(chamber, 'PortHandles');
    delete_line(get_param(pipe_ports.RConn(1), 'Line'));
    add_block('fl_lib/Thermal Liquid/Elements/Flow Resistance (TL)', coldplate, ...
        'Position', [505 265 555 305]);
    resistance_ports = get_param(coldplate, 'PortHandles');
    add_line(model, pipe_ports.RConn(1), resistance_ports.LConn(1), 'autorouting', 'on');
    add_line(model, resistance_ports.RConn(1), chamber_ports.RConn(1), 'autorouting', 'on');
end
set_param(coldplate, 'delta_p_nominal', '29.3', 'delta_p_nominal_unit', 'kPa');
set_param(coldplate, 'mdot_nominal', '0.0332', 'mdot_nominal_unit', 'kg/s');
set_param(coldplate, 'area', '0.00005');

%% 4. Cold plate heat transfer: recalibrated compute_h
% Target: case-to-inlet resistance 0.0267 K/W at 1.6 L/min (Wakefield Thermal 133032).
% In this model R = 1/(mdot*cp) + 1/(h*A), because the CPU exchanges heat with the well-mixed
% chamber at coolant outlet temperature. At 1.6 L/min of water at 45 degC:
%   mdot = 0.02641 kg/s, 1/(mdot*cp) = 0.00906 K/W  ->  h*A = 1/(0.0267 - 0.00906) = 56.7 W/K
% With A = 0.002 m^2 kept as the reference area: h = 28 350 W/m^2K, C = h / mdot^0.8 = 5.19e5.
% h is an effective coefficient on the footprint area (it includes the fin-area gain).
chart = find(sfroot, '-isa', 'Stateflow.EMChart', 'Path', [model '/compute_h']);
chart.Script = sprintf([ ...
    'function h = compute_h(mdot)\n' ...
    '%% Effective cold-plate coefficient on the 0.002 m^2 footprint area.\n' ...
    '%% C calibrated so that R_case-to-inlet = 0.0267 K/W at 1.6 L/min (see README).\n' ...
    'C = 5.19e5;\n' ...
    'n = 0.8;\n' ...
    'h_min = 100;\n' ...
    'h = max(C * abs(mdot)^n, h_min);\n' ...
    'end\n']);

%% 5. Initial conditions consistent with the boundaries (supply temperature, reservoir pressure)
set_param(chamber, 'T_I', T_SUPPLY_K, 'p_I', '1.5', 'p_I_unit', 'bar');
set_param(pipe, 'T0', T_SUPPLY_K);
set_param(cpu, 'T', T_SUPPLY_K);

save_system(model);
close_system(model, 0);
disp('Model correction applied.');
